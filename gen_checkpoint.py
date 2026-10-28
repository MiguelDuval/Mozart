#!/usr/bin/env python3
"""
Generate 12 validation prompts from a single experimental checkpoint and save
matched MIDI files. Self-contained (no JSON report writing), so it survives the
tool process lifecycle. Prompt ids are sourced from the existing matched
evaluation report.

Usage (from repo root, .venv-aura):
    .venv-aura\Scripts\python.exe gen_checkpoint.py \
        --checkpoint .../checkpoint_step_50.pt \
        --midi-dir experiments/aura-midi/eval/runs/eval-antiforget-step50/midi
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"))

import torch  # noqa: E402
from evaluate_models import load_finetuned_model, generate, prompt_seed  # noqa: E402
from miditok import MusicTokenizer  # noqa: E402

MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
REPORT = REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / "eval-matched-20261027" / "evaluation_report.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--midi-dir", required=True)
    ap.add_argument("--max-new", type=int, default=100)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261027)
    ap.add_argument("--prompt-ids", default=None,
                    help="Comma-separated prompt IDs to generate (default: all 12)")
    args = ap.parse_args()

    midi_dir = Path(args.midi_dir)
    midi_dir.mkdir(parents=True, exist_ok=True)

    rep = json.loads(REPORT.read_text())
    pid = {g["prompt_id"]: g["prompt_ids"] for g in rep["generations"]
           if g.get("model") == "pretrained" and g.get("prompt_id")}

    if args.prompt_ids:
        wanted = {s.strip() for s in args.prompt_ids.split(",")}
        pid = {k: v for k, v in pid.items() if k in wanted}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = MusicTokenizer.from_pretrained(str(MODEL_DIR))
    loaded = load_finetuned_model(Path(args.checkpoint), MODEL_DIR, device)
    model = loaded["model"]
    model.eval()

    n = 0
    for prompt_id in sorted(pid.keys()):
        prompt_ids = pid[prompt_id]
        seed = prompt_seed(args.seed, prompt_id)
        ids, score, info = generate(model, tok, prompt_ids, device,
                                    args.max_new, args.temperature, args.top_k, seed)
        out = midi_dir / f"finetuned_{prompt_id}.mid"
        score.dump_midi(str(out))
        n += 1
        print(f"  {prompt_id}: new_tok={info['new_tokens']} eos={info['eos_count']}", flush=True)
    print(f"Generated {n} MIDI files -> {midi_dir}")


if __name__ == "__main__":
    main()