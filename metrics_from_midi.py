#!/usr/bin/env python3
"""
Compute per-generation metrics from a directory of matched MIDI files and emit a
machine-readable JSON summary for Phase J acceptance-gate assessment.

Reads files named {model}_{prompt_id}.mid (e.g. pretrained_gmd-06.mid,
finetuned_gmd-06.mid) and reports notes, duration (beats + seconds), density,
and reopenability, grouped by model and source.

Usage (from repo root, .venv-aura):
    .venv-aura\Scripts\python.exe metrics_from_midi.py \
        --midi-dir experiments/aura-midi/eval/runs/eval-antiforget-step25/midi \
        --prompts experiments/aura-midi/eval/prompts.json \
        --output experiments/aura-midi/eval/runs/eval-antiforget-step25/metrics_from_midi.json
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import symusic  # noqa: E402


def file_metrics(path: Path) -> dict:
    score = symusic.Score(str(path))
    notes = sum(len(tr.notes) for tr in score.tracks)
    end_tick = 0
    for tr in score.tracks:
        for n in tr.notes:
            if n.end > end_tick:
                end_tick = n.end
    tpq = score.tpq
    duration_beats = end_tick / tpq if tpq else 0.0
    # symusic Score exposes tempo via score.tempos; assume default 120 BPM if none
    bpm = score.tempos[0].qpm if score.tempos else 120.0
    duration_sec = duration_beats * 60.0 / bpm if bpm else 0.0
    density = notes / duration_beats if duration_beats else 0.0
    return {
        "notes": int(notes),
        "duration_ticks": int(end_tick),
        "duration_beats": round(duration_beats, 4),
        "duration_sec": round(duration_sec, 4),
        "density": round(density, 4),
        "tracks": len(score.tracks),
        "tpq": int(tpq),
        "valid": True,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--midi-dir", required=True)
    ap.add_argument("--prompts", default=str(REPO_ROOT / "experiments" / "aura-midi" / "eval" / "prompts.json"))
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    prompts = json.loads(Path(args.prompts).read_text())["prompts"]
    prompt_source = {p["prompt_id"]: p["source"] for p in prompts}
    prompt_role = {p["prompt_id"]: p["role_hint"] for p in prompts}

    midi_dir = Path(args.midi_dir)
    files = sorted(midi_dir.glob("*.mid"))

    generations = []
    for f in files:
        m = re.match(r"^(pretrained|finetuned)_(.+)\.mid$", f.name)
        if not m:
            continue
        model, prompt_id = m.group(1), m.group(2)
        try:
            fm = file_metrics(f)
        except Exception as e:
            fm = {"valid": False, "error": str(e)}
        fm.update({
            "model": model,
            "prompt_id": prompt_id,
            "source": prompt_source.get(prompt_id, "unknown"),
            "role_hint": prompt_role.get(prompt_id, "unknown"),
            "midi_path": str(f),
        })
        generations.append(fm)

    # Per model/source summary.
    summary = {}
    for model in ("pretrained", "finetuned"):
        summary[model] = {}
        for source in ("nrgcp", "gmd"):
            gs = [g for g in generations if g.get("model") == model and g.get("source") == source and g.get("valid")]
            if not gs:
                continue
            n = len(gs)
            summary[model][source] = {
                "n_prompts": n,
                "le1_note_prompts": sum(1 for g in gs if g["notes"] <= 1),
                "zero_note_prompts": sum(1 for g in gs if g["notes"] == 0),
                "mean_notes": round(sum(g["notes"] for g in gs) / n, 3),
                "mean_duration_beats": round(sum(g["duration_beats"] for g in gs) / n, 3),
                "mean_duration_sec": round(sum(g["duration_sec"] for g in gs) / n, 3),
                "mean_density": round(sum(g["density"] for g in gs) / n, 4),
                "all_valid": all(g["valid"] for g in gs),
            }

    out = {
        "midi_dir": str(midi_dir),
        "n_files": len(files),
        "generations": generations,
        "summary": summary,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.output} ({len(files)} files)")


if __name__ == "__main__":
    main()