#!/usr/bin/env python3
"""
Anti-forgetting bounded fine-tuning experiment for shikhr/music_maker.

Starts from the ORIGINAL pretrained checkpoint (NOT the degraded 500-step
checkpoint), using a conservative configuration: max 100 steps, lr 1e-6, seed
20261028, batch 1, seq len 128, AdamW, source-balanced NRG-CP/GMD, eval every
25 steps, atomic best/latest checkpoints, finite-loss/grad/param checks.

Usage (from repo root, .venv-aura activated):
    .venv-aura\Scripts\python.exe train_antiforgetting.py
"""

import hashlib
import json
import math
import random
import shutil
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import torch
import safetensors.torch as st

REPO_ROOT = Path(__file__).resolve().parent
MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
RUNS_DIR = REPO_ROOT / "experiments" / "aura-midi" / "runs"
PILOT_RUN_DIR = RUNS_DIR / "pilot-20261027_145544"

sys.path.insert(0, str(MODEL_DIR))

from mgpt_config import MGPTConfig  # noqa: E402
from gpt_model import GPT  # noqa: E402


class TrainConfig:
    run_name: str = "antiforgetting-20261028"
    seed: int = 20261028
    max_steps: int = 100
    batch_size: int = 1
    seq_len: int = 128
    lr: float = 1e-6
    weight_decay: float = 0.01
    grad_clip: float = 1.0
    val_every: int = 25
    source_balance: float = 0.5
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    runs_dir: Path = RUNS_DIR
    token_cache: Path = PILOT_RUN_DIR / "token_cache.json"
    pretrained_ckpt: Path = MODEL_DIR / "model.safetensors"
    pretrained_sha256: str = "38e1083aea069e298f40373ebc394211b66b876702df91b2c4488cbd53079319"
    model_revision: str = "7528164fe0d4fa2625f1bfc126cc8df62791a429"


config = TrainConfig()


def log(message, log_path=None):
    timestamp = datetime.utcnow().isoformat() + "Z"
    line = f"[{timestamp}] {message}\n"
    print(line, end="")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)


def log_err(message, log_path=None):
    timestamp = datetime.utcnow().isoformat() + "Z"
    line = f"[{timestamp}] ERROR: {message}\n"
    print(line, end="")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_file_list(path: Path) -> list:
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


def atomic_torch_save(obj, path: Path):
    tmp_path = str(path) + ".tmp"
    torch.save(obj, tmp_path)
    shutil.move(tmp_path, str(path))


def load_pretrained_model(model_dir: Path, device: torch.device):
    config_path = model_dir / "config.json"
    cfg = MGPTConfig(**json.loads(config_path.read_text()))
    model = GPT(cfg).to(device)
    ckpt = st.load_file(str(model_dir / "model.safetensors"))
    sd = {}
    for k, v in ckpt.items():
        sd[k[6:] if k.startswith("model.") else k] = v
    missing, unexpected = model.load_state_dict(sd, strict=False)
    model.eval()
    return {
        "model": model,
        "config": cfg,
        "ckpt_path": model_dir / "model.safetensors",
        "ckpt_sha256": file_sha256(model_dir / "model.safetensors"),
        "missing": missing,
        "unexpected": unexpected,
    }


class MIDIDataset(torch.utils.data.Dataset):
    def __init__(self, windows):
        self.windows = windows

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        ids = self.windows[idx]
        input_ids = torch.tensor(ids[:-1], dtype=torch.long)
        targets = torch.tensor(ids[1:], dtype=torch.long)
        return input_ids, targets


def balanced_sample(train_nrgcp, train_gmd, balance, rng):
    if rng.random() < balance:
        return train_nrgcp, "nrgcp"
    return train_gmd, "gmd"


def check_parameters_finite(model, step):
    bad = []
    for name, p in model.named_parameters():
        if not torch.isfinite(p.data).all():
            bad.append(name)
    if bad:
        log_err(f"NON-FINITE PARAMETERS at step {step}: {bad[:8]}")
        return False
    return True


def evaluate(model, dataset, source_name, device, log_path):
    model.eval()
    total_loss = 0.0
    num_batches = 0
    with torch.no_grad():
        for i in range(len(dataset)):
            input_ids, targets = dataset[i]
            input_ids = input_ids.unsqueeze(0).to(device)
            targets = targets.unsqueeze(0).to(device)
            _, loss = model(input_ids, targets=targets)
            if not torch.isfinite(loss):
                log_err(f"Non-finite val loss ({source_name}) batch {i}, stopping val early.")
                break
            total_loss += loss.item()
            num_batches += 1
    model.train()
    avg_loss = total_loss / max(num_batches, 1)
    log(f"  Val {source_name}: loss={avg_loss:.4f} ({num_batches} batches)", log_path)
    return avg_loss, num_batches
def main():
    run_tag = f"{config.run_name}-{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS_DIR / run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = run_dir / "checkpoints"
    ckpt_dir.mkdir(exist_ok=True)
    log_path = run_dir / "training.log"

    log(f"=== Anti-forgetting experiment started: {run_tag} ===", log_path)
    log(f"Git HEAD: {_git_head()}", log_path)
    log(f"Run directory: {run_dir}", log_path)
    log(f"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}, device: {config.device}", log_path)
    if torch.cuda.is_available():
        log(f"GPU: {torch.cuda.get_device_name(0)}", log_path)

    # --- Verify pretrained checkpoint provenance ---
    actual_sha = file_sha256(config.pretrained_ckpt)
    log(f"Pretrained ckpt SHA-256: {actual_sha}", log_path)
    if actual_sha != config.pretrained_sha256:
        log_err(f"SHA-256 MISMATCH! Expected {config.pretrained_sha256}, got {actual_sha}", log_path)
        return 1
    log("Pretrained checkpoint SHA-256 verified OK", log_path)

    # --- Cache provenance ---
    if not config.token_cache.exists():
        log_err(f"Token cache missing: {config.token_cache}", log_path)
        return 1
    with open(config.token_cache, "r") as f:
        cache = json.load(f)
    cache_sha = file_sha256(config.token_cache)
    log(f"Token cache: {config.token_cache} (sha256={cache_sha}, seq_len={cache.get('seq_len')})", log_path)
    log(f"Cache counts: nrgcp_train={len(cache.get('nrgcp_train',[]))}, "
        f"nrgcp_val={len(cache.get('nrgcp_val',[]))}, "
        f"gmd_train={len(cache.get('gmd_train',[]))}, "
        f"gmd_val={len(cache.get('gmd_val',[]))}", log_path)

    # --- Reproducibility ---
    random.seed(config.seed)
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    rng = random.Random(config.seed)

    # --- Model: start from ORIGINAL pretrained checkpoint (not the degraded pilot ckpt) ---
    loaded = load_pretrained_model(MODEL_DIR, torch.device(config.device))
    model = loaded["model"]
    log(f"Loaded pretrained model from {loaded['ckpt_path']} (sha={loaded['ckpt_sha256'][:16]}...)", log_path)
    log(f"Missing keys: {loaded['missing']}, Unexpected keys: {loaded['unexpected']}", log_path)
    log(f"Model params: {sum(p.numel() for p in model.parameters()):,}", log_path)
    log(f"Weight tying (wte is lm_head): {model.transformer.wte.weight is model.lm_head.weight}", log_path)

    model_config_record = {
        "vocab_size": loaded["config"].vocab_size,
        "n_layer": loaded["config"].n_layer,
        "n_head": loaded["config"].n_head,
        "n_embd": loaded["config"].n_embd,
        "block_size": loaded["config"].block_size,
        "bias": loaded["config"].bias,
    }

    # --- Datasets (verified pilot manifests + pre-tokenized cache) ---
    train_nrgcp = MIDIDataset(cache["nrgcp_train"])
    train_gmd = MIDIDataset(cache["gmd_train"])
    val_nrgcp = MIDIDataset(cache["nrgcp_val"])
    val_gmd = MIDIDataset(cache["gmd_val"])
    log(f"Train examples: NRG-CP={len(train_nrgcp)}, GMD={len(train_gmd)}", log_path)
    log(f"Val examples: NRG-CP={len(val_nrgcp)}, GMD={len(val_gmd)}", log_path)
    if len(train_nrgcp) == 0 or len(train_gmd) == 0:
        log_err("Empty training dataset — aborting.", log_path)
        return 1

    device = torch.device(config.device)
    model = model.to(device)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    state = {
        "run_name": run_tag,
        "step": 0,
        "max_steps": config.max_steps,
        "seed": config.seed,
        "best_val_loss": float("inf"),
        "train_losses": [],
        "val_losses": [],
        "val_losses_nrgcp": [],
        "val_losses_gmd": [],
        "val_steps": [],
        "timestamps": [],
        "interrupted": False,
        "stop_reason": None,
        "config": {
            "max_steps": config.max_steps,
            "lr": config.lr,
            "weight_decay": config.weight_decay,
            "grad_clip": config.grad_clip,
            "batch_size": config.batch_size,
            "seq_len": config.seq_len,
            "source_balance": config.source_balance,
            "val_every": config.val_every,
            "seed": config.seed,
        },
        "provenance": {
            "pretrained_ckpt": str(config.pretrained_ckpt),
            "pretrained_ckpt_sha256": config.pretrained_sha256,
            "model_revision": config.model_revision,
            "model_config": model_config_record,
            "token_cache": str(config.token_cache),
            "token_cache_sha256": cache_sha,
            "token_cache_counts": {
                "nrgcp_train": len(cache["nrgcp_train"]),
                "nrgcp_val": len(cache["nrgcp_val"]),
                "gmd_train": len(cache["gmd_train"]),
                "gmd_val": len(cache["gmd_val"]),
            },
            "sampling_probabilities": {"nrgcp": config.source_balance, "gmd": 1.0 - config.source_balance},
        },
        "safety": {
            "finite_loss_steps": 0,
            "non_finite_loss_steps": 0,
            "non_finite_grad_steps": 0,
            "non_finite_param_steps": 0,
        },
        "safety_violation": False,
    }

    start_time = time.time()
    interrupted = False

    def signal_handler(signum, frame):
        nonlocal interrupted
        interrupted = True
        log("Interrupt received — will finish current step and save.", log_path)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def save_state():
        state_path = run_dir / "training_state.json"
        tmp_state = str(state_path) + ".tmp"
        with open(tmp_state, "w") as f:
            json.dump(state, f, indent=2, default=str)
        shutil.move(tmp_state, str(state_path))

    def save_checkpoint(name, is_best=False):
        ckpt = {
            "step": state["step"],
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "best_val_loss": state["best_val_loss"],
            "val_loss": state.get("last_val_loss"),
            "config": state["config"],
            "provenance": state["provenance"],
        }
        atomic_torch_save(ckpt, ckpt_dir / f"checkpoint_{name}.pt")
        log(f"Checkpoint saved: {name} (step {state['step']})", log_path)
        if is_best:
            log(f"  -> NEW BEST (combined val_loss={state['best_val_loss']:.4f})", log_path)

    def check_loss_finite(loss, step):
        """Check that the forward-pass loss is finite (called BEFORE backward)."""
        ok = True
        if not torch.isfinite(loss):
            log_err(f"Non-finite loss at step {step}: {loss.item()}", log_path)
            state["safety"]["non_finite_loss_steps"] += 1
            ok = False
        else:
            state["safety"]["finite_loss_steps"] += 1
        return ok

    def check_gradients_finite(step):
        """Check gradient finiteness AFTER backward, BEFORE clip_grad_norm."""
        ok = True
        total_grad_norm = 0.0
        for p in model.parameters():
            if p.grad is not None:
                total_grad_norm += p.grad.data.norm(2).item() ** 2
        total_grad_norm = math.sqrt(total_grad_norm)
        if not math.isfinite(total_grad_norm):
            log_err(f"Non-finite gradient norm at step {step} (before clip)", log_path)
            state["safety"]["non_finite_grad_steps"] += 1
            ok = False
        return ok

    def check_gradients_after_clip(step):
        """Check gradient finiteness AFTER clip_grad_norm, BEFORE optimizer.step."""
        ok = True
        total_grad_norm = 0.0
        for p in model.parameters():
            if p.grad is not None:
                total_grad_norm += p.grad.data.norm(2).item() ** 2
        total_grad_norm = math.sqrt(total_grad_norm)
        if not math.isfinite(total_grad_norm):
            log_err(f"Non-finite gradient norm at step {step} (after clip)", log_path)
            state["safety"]["non_finite_grad_steps"] += 1
            ok = False
        return ok

    def check_parameters_finite(model, step):
        """Check parameter finiteness AFTER optimizer.step(), BEFORE optimizer.zero_grad."""
        bad = []
        for name, p in model.named_parameters():
            if not torch.isfinite(p.data).all():
                bad.append(name)
        if bad:
            log_err(f"NON-FINITE PARAMETERS at step {step}: {bad[:8]}", log_path)
            state["safety"]["non_finite_param_steps"] += 1
            return False
        return True
    try:
        while state["step"] < config.max_steps and not interrupted:
            state["step"] += 1
            step = state["step"]
            step_start = time.time()

            dataset, source = balanced_sample(train_nrgcp, train_gmd, config.source_balance, rng)
            idx = rng.randint(0, len(dataset) - 1)
            input_ids, targets = dataset[idx]
            input_ids = input_ids.unsqueeze(0).to(device)
            targets = targets.unsqueeze(0).to(device)

            logits, loss = model(input_ids, targets=targets)

            if not check_loss_finite(loss, step):
                state["stop_reason"] = f"safety check failed at step {step}"
                state["safety_violation"] = True
                break

            loss.backward()

            if not check_gradients_finite(step):
                state["stop_reason"] = f"safety check failed at step {step}"
                state["safety_violation"] = True
                break

            torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)

            if not check_gradients_after_clip(step):
                state["stop_reason"] = f"safety check failed at step {step}"
                state["safety_violation"] = True
                break

            optimizer.step()

            if not check_parameters_finite(model, step):
                state["stop_reason"] = f"safety check failed at step {step}"
                state["safety_violation"] = True
                break

            optimizer.zero_grad()

            state["train_losses"].append(loss.item())
            step_time = time.time() - step_start
            tokens = config.batch_size * config.seq_len
            state.setdefault("throughput_tokens_per_sec", []).append(tokens / max(step_time, 1e-6))
            peak_vram = (torch.cuda.max_memory_allocated(0) / 1024 ** 2) if torch.cuda.is_available() else 0
            state["peak_vram_mb"] = max(state.get("peak_vram_mb", 0), peak_vram)

            if step % 10 == 0:
                lr = optimizer.param_groups[0]["lr"]
                log(f"  Step {step}/{config.max_steps}: loss={loss.item():.4f}, lr={lr:.2e}, "
                    f"source={source}, {step_time:.2f}s", log_path)

            if step % config.val_every == 0:
                log(f"\n--- Evaluation at step {step} ---", log_path)
                eval_start = time.time()
                val_nrgcp_loss, n_nrg = evaluate(model, val_nrgcp, "NRG-CP", device, log_path)
                val_gmd_loss, n_gmd = evaluate(model, val_gmd, "GMD", device, log_path)
                combined_val = (val_nrgcp_loss + val_gmd_loss) / 2.0

                state["val_losses"].append(combined_val)
                state["val_losses_nrgcp"].append(val_nrgcp_loss)
                state["val_losses_gmd"].append(val_gmd_loss)
                state["val_steps"].append(step)
                state["timestamps"].append(datetime.utcnow().isoformat() + "Z")
                state["last_val_loss"] = combined_val

                log(f"  Combined val loss: {combined_val:.4f} (NRG-CP={val_nrgcp_loss:.4f}, GMD={val_gmd_loss:.4f})", log_path)
                log(f"  Eval time: {time.time() - eval_start:.1f}s", log_path)

                save_checkpoint("latest", is_best=False)
                save_checkpoint(f"step_{step}", is_best=False)
                is_best = combined_val < state["best_val_loss"]
                if is_best:
                    state["best_val_loss"] = combined_val
                    save_checkpoint("best", is_best=True)

                save_state()

            if step >= config.max_steps:
                break

    except Exception as e:
        log_err(f"Fatal exception: {e}", log_path)
        import traceback
        log_err(traceback.format_exc(), log_path)
        state["stop_reason"] = f"fatal exception: {e}"
        state["interrupted"] = True

    # --- Finalize ---
    if not state.get("safety_violation", False):
        save_checkpoint("latest", is_best=False)
    state_path = run_dir / "training_state.json"
    tmp_state = str(state_path) + ".tmp"
    with open(tmp_state, "w") as f:
        json.dump(state, f, indent=2, default=str)
    shutil.move(tmp_state, str(state_path))

    elapsed = time.time() - start_time
    log(f"\n=== ANTI-FORGETTING EXPERIMENT COMPLETE ===", log_path)
    log(f"Completed steps: {state['step']}/{config.max_steps}", log_path)
    log(f"Best val loss: {state['best_val_loss']:.4f}", log_path)
    log(f"Final train loss: {state['train_losses'][-1]:.4f}" if state["train_losses"] else "N/A", log_path)
    log(f"Total elapsed: {elapsed:.1f}s", log_path)
    log(f"Peak VRAM: {state.get('peak_vram_mb', 0):.1f} MB", log_path)
    log(f"Stop reason: {state.get('stop_reason', 'completed normally')}", log_path)
    log(f"Safety: finite_loss={state['safety']['finite_loss_steps']}, "
        f"non_finite_loss={state['safety']['non_finite_loss_steps']}, "
        f"non_finite_grad={state['safety']['non_finite_grad_steps']}, "
        f"non_finite_param={state['safety']['non_finite_param_steps']}", log_path)
    log(f"Run directory: {run_dir}", log_path)

    metrics = {
        "run_name": run_tag,
        "completed_steps": state["step"],
        "max_steps": config.max_steps,
        "best_val_loss": state["best_val_loss"],
        "final_train_loss": state["train_losses"][-1] if state["train_losses"] else None,
        "train_losses": state["train_losses"],
        "val_losses": state["val_losses"],
        "val_losses_nrgcp": state["val_losses_nrgcp"],
        "val_losses_gmd": state["val_losses_gmd"],
        "val_steps": state["val_steps"],
        "timestamps": state["timestamps"],
        "peak_vram_mb": state.get("peak_vram_mb", 0),
        "elapsed_sec": elapsed,
        "stop_reason": state.get("stop_reason"),
        "interrupted": state.get("interrupted", False),
        "config": state["config"],
        "provenance": state["provenance"],
        "safety": state["safety"],
    }
    metrics_path = run_dir / "training_metrics.json"
    tmp_metrics = str(metrics_path) + ".tmp"
    with open(tmp_metrics, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    shutil.move(tmp_metrics, str(metrics_path))
    log(f"Metrics saved to {metrics_path}", log_path)
    return 0


def _git_head() -> str:
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())