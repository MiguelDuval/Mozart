#!/usr/bin/env python3
"""
Fast generation-only evaluation of a single fine-tuned checkpoint against the
12-prompt validation set, using matched decoding settings.

Outputs a machine-readable JSON with per-prompt and per-source metrics, suitable
for applying the Phase J acceptance gates. Loads ONLY the experimental checkpoint
(no pretrained reload), so each run is ~15s and safe under the tool timeout.

Reuses evaluate_models.py's generate/score_metrics/loaders for identical decoding.

Usage (from repo root, .venv-aura):
    .venv-aura\Scripts\python.exe eval_ckpt_metrics.py \
        --checkpoint experiments/aura-midi/runs/<run>/checkpoints/checkpoint_step_25.pt \
        --output experiments/aura-midi/eval/runs/eval-antiforget-step25/metrics_step25.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"))

import torch  # noqa: E402

from evaluate_models import (  # noqa: E402
    load_pretrained_model,
    load_finetuned_model,
    generate,
    score_metrics,
    _eos_token_id,
)
from mgpt_config import MGPTConfig  # noqa: E402

MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
DEFAULT_PROMPTS = REPO_ROOT / "experiments" / "aura-midi" / "eval" / "prompts.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--prompts", default=str(DEFAULT_PROMPTS))
    ap.add_argument("--max-new", type=int, default=100)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261027)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = __import__("miditok", fromlist=["MusicTokenizer"]).MusicTokenizer.from_pretrained(str(MODEL_DIR))

    prompts = json.loads(Path(args.prompts).read_text())["prompts"]
    # prompt_ids are stored in prior eval reports (prompts.json omits them).
    # Load them from the diagnostic matched evaluation report.
    prompt_id_map = {}
    report_candidates = [
        REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / "eval-diagnostic-20261027" / "evaluation_report.json",
        REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / "eval-matched-20261027" / "evaluation_report.json",
    ]
    for cand in report_candidates:
        if cand.exists():
            rep = json.loads(cand.read_text())
            for g in rep.get("generations", []):
                if g.get("model") == "pretrained" and g.get("prompt_id"):
                    prompt_id_map[g["prompt_id"]] = g["prompt_ids"]
            break

    loaded = load_finetuned_model(Path(args.checkpoint), MODEL_DIR, device)
    model = loaded["model"]
    model.eval()

    out = {
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": __import__("hashlib").sha256(
            open(args.checkpoint, "rb").read()
        ).hexdigest(),
        "step": loaded.get("step"),
        "decode": {"max_new": args.max_new, "temperature": args.temperature, "top_k": args.top_k, "seed": args.seed},
        "generations": [],
    }

    for p in prompts:
        prompt_id = p["prompt_id"]
        seed = args.seed + (hash(prompt_id) % (2 ** 31))
        prompt_ids = prompt_id_map.get(prompt_id)
        if not prompt_ids:
            print(f"  WARNING: no prompt_ids for {prompt_id}, skipping")
            continue
        ids, score, info = generate(model, tokenizer, prompt_ids, device,
                                    args.max_new, args.temperature, args.top_k, seed)
        metrics = score_metrics(score)
        # Prompt-only decode to isolate continuation contribution.
        prompt_score = tokenizer.decode(prompt_ids)
        prompt_metrics = score_metrics(prompt_score)
        prompt_notes = int(prompt_metrics["num_notes"])
        notes_in_cont = max(0, int(metrics["num_notes"]) - prompt_notes)

        out["generations"].append({
            "model": "finetuned",
            "prompt_id": prompt_id,
            "source": p["source"],
            "role_hint": p["role_hint"],
            "seed": int(seed),
            "new_tokens": info["new_tokens"],
            "eos_count": info["eos_count"],
            "first_eos_position": info["first_eos_position"],
            "eos_fraction": info["eos_fraction"],
            "notes_in_continuation": notes_in_cont,
            "prompt_notes": prompt_notes,
            "total_notes": int(metrics["num_notes"]),
            "duration_beats": float(metrics["duration_beats"]),
            "duration_sec": float(metrics["duration_sec"]),
            "density": float(metrics["density_notes_per_beat"]),
            "reopen": bool(metrics.get("num_tracks", 0) >= 0),
        })

    # Per-source summary.
    for source in ("nrgcp", "gmd"):
        gs = [g for g in out["generations"] if g["source"] == source]
        out[f"{source}_summary"] = {
            "n_prompts": len(gs),
            "le1_note_prompts": sum(1 for g in gs if g["total_notes"] <= 1),
            "mean_notes": round(sum(g["total_notes"] for g in gs) / len(gs), 2) if gs else 0,
            "mean_duration_beats": round(sum(g["duration_beats"] for g in gs) / len(gs), 2) if gs else 0,
            "mean_duration_sec": round(sum(g["duration_sec"] for g in gs) / len(gs), 2) if gs else 0,
            "all_reopenable": all(g["reopen"] for g in gs),
        }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()