"""
Controlled fine-tuning pilot for shikhr/music_maker.
"""
import sys, os, json, time, hashlib, shutil, random, signal
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart")
MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
RUNS_DIR = REPO_ROOT / "experiments" / "aura-midi" / "runs"
RUN_DIR = RUNS_DIR / "pilot-20261027_145544"
sys.path.insert(0, str(MODEL_DIR))

import torch
import torch.nn as nn
from torch.utils.data import Dataset
import safetensors.torch as st
from mgpt_config import MGPTConfig
from gpt_model import GPT
from miditok import MusicTokenizer
import symusic

CONFIG = {
    "run_name": "pilot-20261027_145544",
    "started_at": datetime.utcnow().isoformat() + "Z",
    "git_head": "d26576d2dd050d73f865d37fc3ebc897eb709623",
    "branch": "feature/mmm-v2-decoder-fix-and-docs",
    "model_revision": "7528164fe0d4fa2625f1bfc126cc8df62791a429",
    "model_sha256": "38e1083aea069e298f40373ebc394211b66b876702df91b2c4488cbd53079319",
    "torch_version": torch.__version__,
    "cuda_available": torch.cuda.is_available(),
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "seed": 20261027,
    "max_steps": 500,
    "batch_size": 1,
    "seq_len": 128,
    "lr": 1e-5,
    "weight_decay": 0.01,
    "grad_clip": 1.0,
    "val_every": 100,
    "fp32": True,
    "data_sources": ["nrgcp", "gmd"],
    "source_balance": 0.5,
    "model_params": 44429824,
    "vocab_size": 12000,
}

random.seed(CONFIG["seed"])
torch.manual_seed(CONFIG["seed"])
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(CONFIG["seed"])

RUN_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR = RUN_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)
GENERATIONS_DIR = RUN_DIR / "generations"
GENERATIONS_DIR.mkdir(exist_ok=True)

log_path = RUN_DIR / "training.log"
err_path = RUN_DIR / "training_error.log"

def log(message):
    timestamp = datetime.utcnow().isoformat() + "Z"
    line = f"[{timestamp}] {message}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")

def log_err(message):
    timestamp = datetime.utcnow().isoformat() + "Z"
    line = f"[{timestamp}] {message}\n"
    with open(err_path, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")

log(f"=== Pilot training started: {CONFIG['run_name']} ===")
log(f"Git HEAD: {CONFIG['git_head']}")
log(f"Model revision: {CONFIG['model_revision']}")
log(f"Model SHA-256: {CONFIG['model_sha256']}")
log(f"PyTorch: {CONFIG['torch_version']}, CUDA: {CONFIG['cuda_available']}")
log(f"Device: {CONFIG['device']}")
log(f"Run directory: {RUN_DIR}")

model_path = MODEL_DIR / "model.safetensors"
sha256_hash = hashlib.sha256()
with open(model_path, "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
        sha256_hash.update(chunk)
actual_sha256 = sha256_hash.hexdigest()
log(f"Model file SHA-256: {actual_sha256}")
if actual_sha256 != CONFIG["model_sha256"]:
    log_err(f"SHA-256 MISMATCH! Expected {CONFIG['model_sha256']}, got {actual_sha256}")
else:
    log("SHA-256 verified OK")

log("Loading tokenizer...")
tokenizer = MusicTokenizer.from_pretrained(str(MODEL_DIR))
log(f"Tokenizer vocab_size: {tokenizer.vocab_size}")

log("Loading model config and architecture...")
config = MGPTConfig(vocab_size=12000, n_embd=512, n_head=8, n_layer=12, block_size=1024, bias=False, dropout=0.1)
model = GPT(config)
total_params = sum(p.numel() for p in model.parameters())
log(f"Model parameters: {total_params:,} ({total_params/1e6:.2f}M)")

log("Loading pretrained checkpoint...")
ckpt = st.load_file(str(model_path))
new_sd = {}
for k, v in ckpt.items():
    if k.startswith("model."):
        k = k[6:]
    new_sd[k] = v
missing, unexpected = model.load_state_dict(new_sd, strict=False)
log(f"Checkpoint keys: {len(ckpt)}, Model keys: {len(model.state_dict())}")
log(f"Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")
log(f"Weight tying: wte is lm_head: {model.transformer.wte.weight is model.lm_head.weight}")

device = torch.device(CONFIG["device"])
model = model.to(device)
model.train()
if torch.cuda.is_available():
    log(f"Peak VRAM after model load: {torch.cuda.max_memory_allocated(0) / 1024**2:.1f} MB")

def load_file_list(path):
    files = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                p = Path(line)
                if not p.is_absolute():
                    p = REPO_ROOT / p
                if p.exists():
                    files.append(str(p))
    return files

nrgcp_train = load_file_list(str(RUNS_DIR / "nrgcp_train_files.txt"))
nrgcp_val = load_file_list(str(RUNS_DIR / "nrgcp_val_files.txt"))
gmd_train = load_file_list(str(RUNS_DIR / "gmd_train_files.txt"))
gmd_val = load_file_list(str(RUNS_DIR / "gmd_val_files.txt"))

log(f"NRG-CP train files: {len(nrgcp_train)}, val: {len(nrgcp_val)}")
log(f"GMD train files: {len(gmd_train)}, val: {len(gmd_val)}")

# Load pre-tokenized cache
cache_path = RUN_DIR / "token_cache.json"
import json as _json
with open(cache_path, "r") as _f:
    _cache = _json.load(_f)
SEQ_LEN = _cache["seq_len"]

class MIDIDataset(Dataset):
    def __init__(self, windows):
        self.windows = windows

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        ids = self.windows[idx]
        input_ids = torch.tensor(ids[:-1], dtype=torch.long)
        targets = torch.tensor(ids[1:], dtype=torch.long)
        return input_ids, targets

log("Loading pre-tokenized datasets from cache...")
train_nrgcp = MIDIDataset(_cache["nrgcp_train"])
train_gmd = MIDIDataset(_cache["gmd_train"])
val_nrgcp = MIDIDataset(_cache["nrgcp_val"])
val_gmd = MIDIDataset(_cache["gmd_val"])

log(f"Train examples: NRG-CP={len(train_nrgcp)}, GMD={len(train_gmd)}")
log(f"Val examples: NRG-CP={len(val_nrgcp)}, GMD={len(val_gmd)}")

def balanced_sample(train_nrgcp, train_gmd, balance=0.5, rng=None):
    if rng is None:
        rng = random
    if rng.random() < balance:
        return train_nrgcp, "nrgcp"
    else:
        return train_gmd, "gmd"

optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG["lr"], weight_decay=CONFIG["weight_decay"])

state = {
    "step": 0,
    "epoch": 0,
    "best_val_loss": float("inf"),
    "train_losses": [],
    "val_losses": [],
    "val_losses_nrgcp": [],
    "val_losses_gmd": [],
    "timestamps": [],
    "throughput_tokens_per_sec": [],
    "peak_vram_mb": 0,
    "config": CONFIG,
}

def save_checkpoint(path, is_best=False):
    tmp_path = str(path) + ".tmp"
    try:
        torch.save({
            "step": state["step"],
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "best_val_loss": state["best_val_loss"],
            "config": CONFIG,
        }, tmp_path)
        shutil.move(tmp_path, str(path))
        log(f"Checkpoint saved: {path.name} (step {state['step']})")
        if is_best:
            log(f"  -> NEW BEST (val_loss={state['best_val_loss']:.4f})")
    except Exception as e:
        log_err(f"Failed to save checkpoint {path}: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def evaluate(dataset, source_name):
    model.eval()
    total_loss = 0.0
    num_batches = 0
    with torch.no_grad():
        for i in range(len(dataset)):
            input_ids, targets = dataset[i]
            input_ids = input_ids.unsqueeze(0).to(device)
            targets = targets.unsqueeze(0).to(device)
            _, loss = model(input_ids, targets=targets)
            total_loss += loss.item()
            num_batches += 1
    model.train()
    avg_loss = total_loss / max(num_batches, 1)
    log(f"  Val {source_name}: loss={avg_loss:.4f} ({num_batches} batches)")
    return avg_loss

def generate_sample(prompt_ids, max_new=100, temperature=1.0, top_k=40):
    model.eval()
    with torch.no_grad():
        idx = torch.tensor([prompt_ids], dtype=torch.long, device=device)
        generated = model.generate(idx, max_new_tokens=max_new, temperature=temperature, top_k=top_k)
        generated_ids = generated[0].cpu().tolist()
    model.train()
    return generated_ids

log("\n=== Generating sample BEFORE training ===")
try:
    before_prompt = train_nrgcp[0][0].tolist()[:32]
    before_ids = generate_sample(before_prompt, max_new=100)
    before_score = tokenizer.decode(before_ids)
    before_midi = GENERATIONS_DIR / "sample_before.mid"
    before_score.dump_midi(str(before_midi))
    log(f"  Before sample saved: {before_midi}")
    log(f"  Before generated: {len(before_ids)} tokens")
except Exception as e:
    log_err(f"Before generation failed: {e}")

log("\n=== Starting training loop ===")
start_time = time.time()
tokens_processed = 0
interrupted = False

def signal_handler(signum, frame):
    global interrupted
    interrupted = True
    log("Interrupt received, will finish current step and save...")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

rng = random.Random(CONFIG["seed"])

try:
    while state["step"] < CONFIG["max_steps"] and not interrupted:
        state["step"] += 1
        step_start = time.time()

        dataset, source = balanced_sample(train_nrgcp, train_gmd, CONFIG["source_balance"], rng)
        idx = rng.randint(0, len(dataset) - 1)
        input_ids, targets = dataset[idx]
        input_ids = input_ids.unsqueeze(0).to(device)
        targets = targets.unsqueeze(0).to(device)

        logits, loss = model(input_ids, targets=targets)

        if not torch.isfinite(loss):
            log_err(f"Non-finite loss at step {state['step']}, stopping.")
            break

        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), CONFIG["grad_clip"])

        grad_finite = all(
            p.grad is None or torch.isfinite(p.grad).all()
            for p in model.parameters()
        )
        if not grad_finite:
            log_err(f"Non-finite gradients at step {state['step']}, skipping optimizer step.")
            optimizer.zero_grad()
            continue

        optimizer.step()
        optimizer.zero_grad()

        train_loss = loss.item()
        state["train_losses"].append(train_loss)
        step_time = time.time() - step_start
        tokens_processed += CONFIG["batch_size"] * CONFIG["seq_len"]

        if torch.cuda.is_available():
            peak_vram = torch.cuda.max_memory_allocated(0) / 1024**2
            state["peak_vram_mb"] = max(state["peak_vram_mb"], peak_vram)

        elapsed = time.time() - start_time
        throughput = tokens_processed / elapsed if elapsed > 0 else 0
        state["throughput_tokens_per_sec"].append(throughput)

        if state["step"] % 10 == 0 or state["step"] == 1:
            log(f"Step {state['step']:3d}/{CONFIG['max_steps']} | "
                f"loss={train_loss:.4f} | source={source} | "
                f"step_time={step_time*1000:.0f}ms | "
                f"throughput={throughput:.1f} tok/s | "
                f"elapsed={elapsed:.0f}s")

        if state["step"] % CONFIG["val_every"] == 0 or state["step"] == CONFIG["max_steps"]:
            log(f"\n--- Evaluation at step {state['step']} ---")
            eval_start = time.time()

            val_nrgcp_loss = evaluate(val_nrgcp, "NRG-CP")
            val_gmd_loss = evaluate(val_gmd, "GMD")
            combined_val = (val_nrgcp_loss + val_gmd_loss) / 2.0

            state["val_losses"].append(combined_val)
            state["val_losses_nrgcp"].append(val_nrgcp_loss)
            state["val_losses_gmd"].append(val_gmd_loss)
            state["timestamps"].append(datetime.utcnow().isoformat() + "Z")

            log(f"  Combined val loss: {combined_val:.4f}")
            log(f"  Eval time: {time.time() - eval_start:.1f}s")

            save_checkpoint(CHECKPOINT_DIR / "checkpoint_latest.pt")

            is_best = combined_val < state["best_val_loss"]
            if is_best:
                state["best_val_loss"] = combined_val
                save_checkpoint(CHECKPOINT_DIR / "checkpoint_best.pt", is_best=True)

            state_path = RUN_DIR / "training_state.json"
            tmp_state = str(state_path) + ".tmp"
            with open(tmp_state, "w") as f:
                json.dump(state, f, indent=2)
            shutil.move(tmp_state, str(state_path))

            log(f"  Training state saved.")

except Exception as e:
    log_err(f"Fatal exception: {e}")
    import traceback
    log_err(traceback.format_exc())

log("\n=== Saving final state ===")
save_checkpoint(CHECKPOINT_DIR / "checkpoint_latest.pt")
state_path = RUN_DIR / "training_state.json"
tmp_state = str(state_path) + ".tmp"
with open(tmp_state, "w") as f:
    json.dump(state, f, indent=2)
shutil.move(tmp_state, str(state_path))

log("\n=== Generating sample AFTER training ===")
try:
    after_prompt = train_nrgcp[0][0].tolist()[:32]
    after_ids = generate_sample(after_prompt, max_new=100)
    after_score = tokenizer.decode(after_ids)
    after_midi = GENERATIONS_DIR / "sample_after.mid"
    after_score.dump_midi(str(after_midi))
    log(f"  After sample saved: {after_midi}")
    log(f"  After generated: {len(after_ids)} tokens")
except Exception as e:
    log_err(f"After generation failed: {e}")

elapsed = time.time() - start_time
log("\n=== PILOT TRAINING COMPLETE ===")
log(f"Total steps: {state['step']}/{CONFIG['max_steps']}")
log(f"Best val loss: {state['best_val_loss']:.4f}")
log(f"Final train loss: {state['train_losses'][-1]:.4f}" if state['train_losses'] else "N/A")
log(f"Total elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
log(f"Peak VRAM: {state['peak_vram_mb']:.1f} MB")
log(f"Average throughput: {sum(state['throughput_tokens_per_sec'])/max(len(state['throughput_tokens_per_sec']),1):.1f} tok/s")
log(f"Run directory: {RUN_DIR}")

metrics = {
    "run_name": CONFIG["run_name"],
    "completed_steps": state["step"],
    "max_steps": CONFIG["max_steps"],
    "best_val_loss": state["best_val_loss"],
    "final_train_loss": state["train_losses"][-1] if state["train_losses"] else None,
    "val_losses": state["val_losses"],
    "val_losses_nrgcp": state["val_losses_nrgcp"],
    "val_losses_gmd": state["val_losses_gmd"],
    "timestamps": state["timestamps"],
    "peak_vram_mb": state["peak_vram_mb"],
    "elapsed_sec": elapsed,
    "config": CONFIG,
    "interrupted": interrupted,
}
metrics_path = RUN_DIR / "training_metrics.json"
tmp_metrics = str(metrics_path) + ".tmp"
with open(tmp_metrics, "w") as f:
    json.dump(metrics, f, indent=2)
shutil.move(tmp_metrics, str(metrics_path))
log(f"Metrics saved to {metrics_path}")