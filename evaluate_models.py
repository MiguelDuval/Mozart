"""
Baseline-vs-fine-tuned evaluator for shikhr/music_maker (Mozart project).

Generates MIDI from the original pretrained checkpoint and a selected
fine-tuned checkpoint under *matched conditions*:

  * same verified tokenizer (shikhr/music_maker)
  * same decoding implementation and configuration
  * same fixed prompt set (validation material only)
  * fixed and recorded random seeds

For every generated file it records the model checkpoint, prompt identity,
seed, decoding settings and tokenizer revision, and writes a machine-readable
JSON report plus valid MIDI samples.

Usage (from repo root):
    .venv-aura/Scripts/python.exe evaluate_models.py \
        --pretrained experiments/aura-midi/models/shikhr-music-maker-official \
        --finetuned  experiments/aura-midi/runs/pilot-20261027_145544/checkpoints/checkpoint_best.pt \
        --output-dir experiments/aura-midi/eval/runs/eval-20261027 \
        --max-new 100 --temperature 1.0 --top-k 40 --seed 20261027
"""

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import safetensors.torch as st
import symusic
import torch

REPO_ROOT = Path(__file__).resolve().parent
MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
DEFAULT_FINETUNED = (
    REPO_ROOT
    / "experiments"
    / "aura-midi"
    / "runs"
    / "pilot-20261027_145544"
    / "checkpoints"
    / "checkpoint_best.pt"
)
DEFAULT_PROMPTS = (
    REPO_ROOT / "experiments" / "aura-midi" / "eval" / "prompts.json"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / f"eval-{int(time.time())}"
)

sys.path.insert(0, str(MODEL_DIR))

from mgpt_config import MGPTConfig  # noqa: E402
from gpt_model import GPT  # noqa: E402
from miditok import MusicTokenizer  # noqa: E402


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def prompt_seed(base_seed: int, prompt_id: str) -> int:
    """Deterministic per-prompt seed derived from sha256(prompt_id).

    Python's built-in ``hash()`` is salted per process (PYTHONHASHSEED), so it
    must never be used for experiment seeds: the same prompt would get a
    different seed in every process. sha256 is stable across processes and
    runs, which is what generation reproducibility requires.
    """
    return base_seed + (int(hashlib.sha256(prompt_id.encode("utf-8")).hexdigest(), 16) % (2 ** 31))


def load_tokenizer(model_dir: Path) -> MusicTokenizer:
    tok = MusicTokenizer.from_pretrained(str(model_dir))
    return tok


def build_model(config: MGPTConfig, device: torch.device) -> GPT:
    model = GPT(config)
    return model.to(device)


def load_pretrained_model(model_dir: Path, device: torch.device):
    """Load the original pretrained checkpoint (safetensors) into GPT."""
    config_path = model_dir / "config.json"
    config = MGPTConfig(**json.loads(config_path.read_text()))
    model = build_model(config, device)
    ckpt_path = model_dir / "model.safetensors"
    ckpt = st.load_file(str(ckpt_path))
    sd = {}
    for k, v in ckpt.items():
        sd[k[6:] if k.startswith("model.") else k] = v
    # The official shikhr/music_maker safetensors stores lm_head.weight but not
    # transformer.wte.weight: the GPT ties wte <-> lm_head in __init__, so loading
    # lm_head.weight already initialises the shared embedding tensor. Promoting
    # lm_head.weight into sd["transformer.wte.weight"] makes load_state_dict report
    # missing == [] and unexpected == [] (without it, "transformer.wte.weight" would
    # be listed as missing even though its value is loaded through the tied lm_head).
    if "transformer.wte.weight" not in sd and "lm_head.weight" in sd:
        sd["transformer.wte.weight"] = sd["lm_head.weight"]
    missing, unexpected = model.load_state_dict(sd, strict=False)
    model.eval()
    return {
        "model": model,
        "config": config,
        "ckpt_path": ckpt_path,
        "ckpt_sha256": file_sha256(ckpt_path),
        "missing": missing,
        "unexpected": unexpected,
    }


def load_finetuned_model(checkpoint_path: Path, model_dir: Path, device: torch.device):
    """Load a fine-tuned torch checkpoint (model_state_dict) into GPT.

    The official config.json defines the architecture; the fine-tuned file
    only carries the trained state dict (+ optimizer/training bookkeeping).

    Uses ``weights_only=True`` with a ``TorchVersion`` safe global, as required
    by PyTorch 2.6's stricter ``torch.load`` defaults.
    """
    from torch.serialization import safe_globals

    config_path = model_dir / "config.json"
    config = MGPTConfig(**json.loads(config_path.read_text()))
    model = build_model(config, device)
    with safe_globals([torch.torch_version.TorchVersion]):
        ckpt = torch.load(str(checkpoint_path), map_location=device, weights_only=True)
    sd = ckpt["model_state_dict"] if isinstance(ckpt, dict) and "model_state_dict" in ckpt else ckpt
    missing, unexpected = model.load_state_dict(sd, strict=False)
    model.eval()
    return {
        "model": model,
        "config": config,
        "ckpt_path": checkpoint_path,
        "ckpt_sha256": file_sha256(checkpoint_path),
        "step": ckpt.get("step") if isinstance(ckpt, dict) else None,
        "best_val_loss": ckpt.get("best_val_loss") if isinstance(ckpt, dict) else None,
        "missing": missing,
        "unexpected": unexpected,
    }



# ---------------------------------------------------------------------------
# Prompt set (validation material only)
# ---------------------------------------------------------------------------


def _read_file_list(path: Path) -> list:
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


def build_prompts_from_validation(runs_dir: Path, n_per_source: int = 6, prompt_len: int = 32,
                                  tokenizer: MusicTokenizer = None) -> list:
    """Build a fixed prompt set from validation material (never test material).

    Returns a list of prompt dicts with stable identities. Prompts are the
    first `prompt_len` token ids of a validation MIDI, balanced between
    NRG-CP (chord-oriented) and GMD (drum-oriented).
    """
    nrgcp_val = _read_file_list(runs_dir / "nrgcp_val_files.txt")
    gmd_val = _read_file_list(runs_dir / "gmd_val_files.txt")

    rng = random.Random(20261027)
    nrgcp_picks = rng.sample(nrgcp_val, min(n_per_source, len(nrgcp_val)))
    gmd_picks = rng.sample(gmd_val, min(n_per_source, len(gmd_val)))

    prompts = []
    pid = 0
    for source, picks in (("nrgcp", nrgcp_picks), ("gmd", gmd_picks)):
        for fpath in picks:
            try:
                score = symusic.Score(fpath)
                ids = tokenizer.encode(score).ids
            except Exception as e:
                print(f"  [skip] {fpath}: {e}")
                continue
            if len(ids) < prompt_len + 1:
                continue
            prompt_ids = ids[:prompt_len]
            prompts.append({
                "prompt_id": f"{source}-{pid:02d}",
                "source": source,
                "midi_file": fpath,
                "prompt_len": len(prompt_ids),
                "prompt_ids": prompt_ids,
                "total_tokens": len(ids),
                "role_hint": "chord-oriented" if source == "nrgcp" else "drum-oriented",
            })
            pid += 1

    prompts.sort(key=lambda p: p["prompt_id"])
    return prompts


def load_or_build_prompts(prompts_path: Path, runs_dir: Path, tokenizer: MusicTokenizer,
                          n_per_source: int = 6, prompt_len: int = 32) -> list:
    if prompts_path.exists():
        data = json.loads(prompts_path.read_text())
        prompts = data["prompts"]
        for p in prompts:
            if "prompt_ids" not in p or not p["prompt_ids"]:
                # Re-derive prompt ids from the source midi file (provenance fallback).
                score = symusic.Score(p["midi_file"])
                p["prompt_ids"] = tokenizer.encode(score).ids[: p.get("prompt_len", 32)]
            else:
                p["prompt_ids"] = list(p["prompt_ids"])
        print(f"Loaded {len(prompts)} prompts from {prompts_path}")
        return prompts
    print(f"Prompts file not found; building from validation material in {runs_dir}")
    prompts = build_prompts_from_validation(runs_dir, n_per_source=n_per_source,
                                            prompt_len=prompt_len, tokenizer=tokenizer)
    prompts_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep prompt_ids in the saved file for full provenance.
    prompts_path.write_text(json.dumps({"prompts": prompts}, indent=2))
    print(f"Built and saved {len(prompts)} prompts to {prompts_path}")
    return prompts


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _eos_token_id(tokenizer: MusicTokenizer) -> int:
    """Resolve the EOS_None token id from the tokenizer vocabulary (fallback 2)."""
    try:
        return int(tokenizer.vocab.get("EOS_None", 2))
    except Exception:
        return 2


def generate(model: GPT, tokenizer: MusicTokenizer, prompt_ids: list, device: torch.device,
             max_new: int, temperature: float, top_k: int, seed: int):
    """Generate a continuation deterministically. Returns (ids, score, info).

    ``info`` records termination-relevant facts about the produced continuation:
    the model's ``generate()`` has no internal EOS stop and always emits exactly
    ``max_new`` tokens, so any early "termination" is visible at token level as
    EOS_None tokens (which the tokenizer decodes to silence / no notes).
    """
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model.eval()
    with torch.no_grad():
        idx = torch.tensor([prompt_ids], dtype=torch.long, device=device)
        generated = model.generate(
            idx, max_new_tokens=max_new, temperature=temperature, top_k=top_k
        )
        ids = generated[0].cpu().tolist()
    prompt_len = len(prompt_ids)
    continuation = ids[prompt_len:]
    eos_id = _eos_token_id(tokenizer)
    eos_positions = [i for i, t in enumerate(continuation) if t == eos_id]
    info = {
        "new_tokens": len(continuation),
        "max_new_requested": max_new,
        "model_early_termination": len(continuation) < max_new,
        "eos_id": eos_id,
        "eos_count": len(eos_positions),
        "first_eos_position": eos_positions[0] if eos_positions else None,
        "eos_positions": eos_positions,
        "eos_fraction": round(len(eos_positions) / len(continuation), 4) if continuation else 0.0,
    }
    score = tokenizer.decode(ids)
    return ids, score, info


# ---------------------------------------------------------------------------
# MIDI / musical-time helpers
# ---------------------------------------------------------------------------


def tempo_map(score: symusic.Score):
    """Return sorted list of (tick, qpm) from the score tempo map."""
    tm = []
    for t in score.tempos:
        tm.append((int(t.time), float(t.qpm)))
    tm.sort()
    if not tm:
        tm = [(0, 120.0)]
    return tm


def ticks_to_seconds(tick: int, tm: list, tpq: int) -> float:
    """Convert a tick position to seconds using a piecewise-constant tempo map."""
    seconds = 0.0
    prev_tick = 0
    prev_qpm = tm[0][1]
    for tick_i, qpm in tm:
        if tick_i <= prev_tick:
            prev_qpm = qpm
            continue
        if tick <= tick_i:
            seconds += (tick - prev_tick) / tpq * (60.0 / prev_qpm)
            return seconds
        seconds += (tick_i - prev_tick) / tpq * (60.0 / prev_qpm)
        prev_tick = tick_i
        prev_qpm = qpm
    seconds += (tick - prev_tick) / tpq * (60.0 / prev_qpm)
    return seconds


def extract_notes(score: symusic.Score):
    """Flatten all tracks into note dicts with tick + musical time."""
    tm = tempo_map(score)
    tpq = score.tpq
    notes = []
    for tr_idx, tr in enumerate(score.tracks):
        for n in tr.notes:
            notes.append({
                "track": tr_idx,
                "program": int(tr.program),
                "is_drum": bool(tr.is_drum),
                "pitch": int(n.pitch),
                "velocity": int(n.velocity),
                "start_tick": int(n.start),
                "end_tick": int(n.end),
                "start_beats": int(n.start) / tpq,
                "end_beats": int(n.end) / tpq,
                "duration_beats": int(n.end - n.start) / tpq,
                "start_sec": ticks_to_seconds(int(n.start), tm, tpq),
                "end_sec": ticks_to_seconds(int(n.end), tm, tpq),
                "duration_sec": ticks_to_seconds(int(n.end), tm, tpq)
                    - ticks_to_seconds(int(n.start), tm, tpq),
            })
    notes.sort(key=lambda x: (x["start_tick"], x["pitch"]))
    return notes


def _track_role(program: int, is_drum: bool) -> str:
    """Map a MIDI program + drum flag to a coarse musical role.

    GM program ranges (0-127). Not ground truth: a program number is only an
    instrument hint, not a functional arrangement role. Used for compact
    role reporting in evaluation reports, never for model supervision.
    """
    if is_drum:
        return "rhythm"
    if 32 <= program <= 39:
        return "bass"
    if 80 <= program <= 87:
        return "lead"
    if 88 <= program <= 95:
        return "pad"
    if 0 <= program <= 7:
        return "harmony"
    if 24 <= program <= 31:
        return "harmony"
    return "other"


def _role_hint_matches(role_hint: str, track_roles: list[str]) -> bool | None:
    """Compare a declared role_hint with observed track roles.

    Returns True if at least one track role is compatible with the hint,
    False if clearly incompatible, None when no musical tracks exist.
    Role hints are free-text from the dataset; this is a coarse sanity check,
    not ground-truth supervision.
    """
    if not track_roles:
        return None
    hint = role_hint.lower()
    compatible = {
        "drum": {"rhythm"},
        "chord": {"harmony"},
        "harmony": {"harmony"},
        "bass": {"bass"},
        "lead": {"lead"},
        "pad": {"pad"},
        "melody": {"lead"},
        "arpeggio": {"harmony", "lead"},
    }
    for key, roles in compatible.items():
        if key in hint:
            return any(r in roles for r in track_roles)
    # Unrecognized hint: cannot confirm or deny.
    return None


def score_metrics(score: symusic.Score) -> dict:
    """Compute musical-time metrics for a score. TPQ-normalized."""
    tm = tempo_map(score)
    tpq = score.tpq
    notes = extract_notes(score)

    last_tick = max((n["end_tick"] for n in notes), default=0)
    duration_ticks = last_tick
    duration_beats = last_tick / tpq if tpq else 0.0
    duration_sec = ticks_to_seconds(last_tick, tm, tpq)

    pitches = [n["pitch"] for n in notes]
    velocities = [n["velocity"] for n in notes]

    # Polyphony: max simultaneous notes (sweep line over start/end ticks).
    events = []
    for n in notes:
        events.append((n["start_tick"], 1))
        events.append((n["end_tick"], -1))
    events.sort()
    cur = 0
    max_poly = 0
    for _, delta in events:
        cur += delta
        max_poly = max(max_poly, cur)

    density = len(notes) / duration_beats if duration_beats > 0 else 0.0

    pitch_range = (min(pitches), max(pitches)) if pitches else (0, 0)
    vel_range = (min(velocities), max(velocities)) if velocities else (0, 0)

    silence_beats = 0.0
    prev_end = 0.0
    for n in notes:
        if n["start_beats"] > prev_end:
            silence_beats += n["start_beats"] - prev_end
        prev_end = max(prev_end, n["end_beats"])
    trailing_silence_beats = duration_beats - prev_end if duration_beats > prev_end else 0.0

    bigrams = []
    for i in range(len(notes) - 1):
        bigrams.append((notes[i]["pitch"], round(notes[i]["duration_beats"], 3),
                        notes[i + 1]["pitch"], round(notes[i + 1]["duration_beats"], 3)))
    repeat_count = len(bigrams) - len(set(bigrams)) if bigrams else 0
    repeat_frac = repeat_count / len(bigrams) if bigrams else 0.0

    tracks = []
    for tr_idx, tr in enumerate(score.tracks):
        tnotes = [n for n in notes if n["track"] == tr_idx]
        tracks.append({
            "index": tr_idx,
            "program": int(tr.program),
            "is_drum": bool(tr.is_drum),
            "role": _track_role(int(tr.program), bool(tr.is_drum)),
            "notes": len(tnotes),
        })

    return {
        "tpq": int(tpq),
        "num_tracks": len(score.tracks),
        "num_notes": len(notes),
        "duration_ticks": int(duration_ticks),
        "duration_beats": round(duration_beats, 4),
        "duration_sec": round(duration_sec, 4),
        "density_notes_per_beat": round(density, 4),
        "max_polyphony": int(max_poly),
        "pitch_range": list(pitch_range),
        "velocity_range": list(vel_range),
        "silence_beats": round(silence_beats, 4),
        "trailing_silence_beats": round(trailing_silence_beats, 4),
        "repeat_bigram_fraction": round(repeat_frac, 4),
        "tracks": tracks,
    }


def midi_valid_and_reopenable(path: Path) -> dict:
    """Re-open a saved MIDI and report validity + basic stats."""
    try:
        score = symusic.Score(str(path))
        notes = sum(len(tr.notes) for tr in score.tracks)
        return {"valid": True, "reopened": True, "tpq": int(score.tpq),
                "tracks": len(score.tracks), "notes": int(notes)}
    except Exception as e:
        return {"valid": False, "reopened": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tokenizer fidelity (separate from model quality)
# ---------------------------------------------------------------------------


def tokenizer_fidelity_check(tokenizer: MusicTokenizer, val_files: list) -> dict:
    """Round-trip encode/decode/re-encode on validation material only.

    This answers: does the tokenizer faithfully represent/reconstruct MIDI?
    It is reported separately from model generation quality.
    """
    results = []
    for fpath in val_files[:8]:
        try:
            score = symusic.Score(fpath)
            tok1 = tokenizer.encode(score)
            dec = tokenizer.decode(tok1.ids)
            tok2 = tokenizer.encode(dec)
            orig_notes = sum(len(tr.notes) for tr in score.tracks)
            dec_notes = sum(len(tr.notes) for tr in dec.tracks)
            results.append({
                "file": fpath,
                "orig_tokens": len(tok1.ids),
                "orig_notes": orig_notes,
                "decoded_notes": dec_notes,
                "reencoded_tokens": len(tok2.ids),
                "note_match": orig_notes == dec_notes,
                "token_match": len(tok1.ids) == len(tok2.ids),
            })
        except Exception as e:
            results.append({"file": fpath, "error": str(e)})
    all_note_match = all(r.get("note_match", False) for r in results if "error" not in r)
    all_token_match = all(r.get("token_match", False) for r in results if "error" not in r)
    return {
        "files_checked": len(results),
        "all_note_count_match": bool(all_note_match),
        "all_token_count_match": bool(all_token_match),
        "details": results,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def build_report(args, tokenizer, pretrained_meta, finetuned_meta, prompts,
                 generations, fidelity, elapsed_sec) -> dict:
    return {
        "evaluator": "evaluate_models.py",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess_git_head(),
        "branch": subprocess_git_branch(),
        "command_line": {k: (str(v) if isinstance(v, Path) else v)
                         for k, v in vars(args).items()},
        "tokenizer": {
            "dir": str(MODEL_DIR),
            "tokenizer_json": str(MODEL_DIR / "tokenizer.json"),
            "vocab_size": tokenizer.vocab_size,
            "revision_sha256": file_sha256(MODEL_DIR / "tokenizer.json"),
        },
        "models": {
            "pretrained": {
                "ckpt_path": str(pretrained_meta["ckpt_path"]),
                "ckpt_sha256": pretrained_meta["ckpt_sha256"],
                "config": {
                    "vocab_size": pretrained_meta["config"].vocab_size,
                    "n_layer": pretrained_meta["config"].n_layer,
                    "n_head": pretrained_meta["config"].n_head,
                    "n_embd": pretrained_meta["config"].n_embd,
                    "block_size": pretrained_meta["config"].block_size,
                    "bias": pretrained_meta["config"].bias,
                },
                "missing_keys": pretrained_meta["missing"],
                "unexpected_keys": pretrained_meta["unexpected"],
            },
            "finetuned": {
                "ckpt_path": str(finetuned_meta["ckpt_path"]),
                "ckpt_sha256": finetuned_meta["ckpt_sha256"],
                "step": finetuned_meta["step"],
                "best_val_loss": finetuned_meta["best_val_loss"],
                "config": {
                    "vocab_size": finetuned_meta["config"].vocab_size,
                    "n_layer": finetuned_meta["config"].n_layer,
                    "n_head": finetuned_meta["config"].n_head,
                    "n_embd": finetuned_meta["config"].n_embd,
                    "block_size": finetuned_meta["config"].block_size,
                    "bias": finetuned_meta["config"].bias,
                },
                "missing_keys": finetuned_meta["missing"],
                "unexpected_keys": finetuned_meta["unexpected"],
            },
        },
        "decoding": {
            "max_new": args.max_new,
            "temperature": args.temperature,
            "top_k": args.top_k,
            "seed": args.seed,
        },
        "prompts": prompts,
        "generations": generations,
        "tokenizer_fidelity": fidelity,
        "elapsed_sec": round(elapsed_sec, 2),
    }


def subprocess_git_head():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                       text=True).strip()
    except Exception:
        return None


def subprocess_git_branch():
    try:
        return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT,
                                       text=True).strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="Baseline-vs-fine-tuned MIDI generation evaluator")
    ap.add_argument("--pretrained", type=Path, default=MODEL_DIR,
                    help="Directory with the official pretrained model (config.json + model.safetensors)")
    ap.add_argument("--finetuned", type=Path, default=DEFAULT_FINETUNED,
                    help="Path to the fine-tuned torch checkpoint")
    ap.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS,
                    help="Prompt set JSON (built from validation material if absent)")
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                    help="Directory for MIDI samples + JSON report")
    ap.add_argument("--runs-dir", type=Path,
                    default=REPO_ROOT / "experiments" / "aura-midi" / "runs",
                    help="Runs dir containing nrgcp_val_files.txt / gmd_val_files.txt")
    ap.add_argument("--prompts-per-source", type=int, default=6,
                    help="Prompts per source when building the prompt set")
    ap.add_argument("--prompt-len", type=int, default=32,
                    help="Prompt length in tokens")
    ap.add_argument("--max-new", type=int, default=100,
                    help="Max new tokens to generate")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261027)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    device = torch.device(args.device)
    print(f"Device: {device}")
    print(f"Tokenizer dir: {args.pretrained}")

    tokenizer = load_tokenizer(args.pretrained)
    print(f"Tokenizer vocab_size: {tokenizer.vocab_size}")

    prompts = load_or_build_prompts(args.prompts, args.runs_dir, tokenizer,
                                    args.prompts_per_source, args.prompt_len)
    full_path = args.prompts.with_suffix(".full.json")
    if full_path.exists():
        full = json.loads(full_path.read_text())["prompts"]
        id_map = {p["prompt_id"]: p["prompt_ids"] for p in full}
        for p in prompts:
            if not p.get("prompt_ids"):
                p["prompt_ids"] = id_map.get(p["prompt_id"], [])

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    midi_dir = output_dir / "midi"
    midi_dir.mkdir(parents=True, exist_ok=True)

    total_start = time.time()
    generations = []


    for model_name, loader in (("pretrained", lambda: load_pretrained_model(args.pretrained, device)),
                               ("finetuned", lambda: load_finetuned_model(args.finetuned, args.pretrained, device))):
        print(f"\n=== Generating with {model_name} model ===")
        loaded = loader()
        model = loaded["model"]
        for p in prompts:
            prompt_id = p["prompt_id"]
            seed = prompt_seed(args.seed, prompt_id)
            print(f"  [{model_name}] {prompt_id} (seed={seed}) ...")
            t0 = time.time()
            ids, score, gen_info = generate(model, tokenizer, p["prompt_ids"], device,
                                            args.max_new, args.temperature, args.top_k, seed)
            gen_time = time.time() - t0

            midi_path = midi_dir / f"{model_name}_{prompt_id}.mid"
            score.dump_midi(str(midi_path))

            metrics = score_metrics(score)
            reopen = midi_valid_and_reopenable(midi_path)

            # Role consistency: compare the declared role_hint (from prompts)
            # with the coarse roles observed in the generated tracks.
            track_roles = [t["role"] for t in metrics["tracks"] if t["notes"] > 0]
            role_hint = p["role_hint"]
            role_matches_declared = _role_hint_matches(role_hint, track_roles)

            # Prompt-only decode: how much of the decoded score comes from the
            # prompt itself vs. the generated continuation. The difference is the
            # best available proxy for "notes contributed by the continuation".
            prompt_score = tokenizer.decode(p["prompt_ids"])
            prompt_metrics = score_metrics(prompt_score)
            prompt_notes = int(prompt_metrics["num_notes"])
            notes_in_continuation = max(0, int(metrics["num_notes"]) - prompt_notes)

            generations.append({
                "model": model_name,
                "prompt_id": prompt_id,
                "source": p["source"],
                "role_hint": p["role_hint"],
                "seed": int(seed),
                "decode": {
                    "max_new": args.max_new,
                    "temperature": args.temperature,
                    "top_k": args.top_k,
                },
                "prompt_ids": p["prompt_ids"],
                "prompt_len": p["prompt_len"],
                "generated_token_count": len(ids),
                "new_tokens": len(ids) - p["prompt_len"],
                "termination": gen_info,
                "prompt_notes": prompt_notes,
                "prompt_duration_beats": prompt_metrics["duration_beats"],
                "notes_in_continuation": int(notes_in_continuation),
                "midi_path": str(midi_path),
                "midi_rel_path": str(midi_path.relative_to(REPO_ROOT)),
                "generation_sec": round(gen_time, 3),
                "metrics": metrics,
                "reopen": reopen,
                "track_roles": track_roles,
                "role_matches_declared": role_matches_declared,
            })
        # Free GPU memory before loading the next model.
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Tokenizer fidelity check on validation material (separate from model quality).
    val_files = _read_file_list(args.runs_dir / "nrgcp_val_files.txt") + \
                _read_file_list(args.runs_dir / "gmd_val_files.txt")
    fidelity = tokenizer_fidelity_check(tokenizer, val_files)

    elapsed = time.time() - total_start

    # Capture model metadata (load on CPU to avoid holding GPU weights twice).
    pretrained_meta = load_pretrained_model(args.pretrained, torch.device("cpu"))
    finetuned_meta = load_finetuned_model(args.finetuned, args.pretrained, torch.device("cpu"))

    report = build_report(args, tokenizer, pretrained_meta, finetuned_meta, prompts,
                          generations, fidelity, elapsed)

    report_path = output_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport written to {report_path}")
    print(f"MIDI samples in {midi_dir}")
    print(f"Total elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()

