#!/usr/bin/env python3
"""
Independent verification of MIDI evaluation metrics (Phase N).

Recomputes per-generation metrics directly from MIDI files using symusic,
without relying on metrics_from_midi.py, and cross-checks the results.

Usage (from repo root, .venv-aura):
    .venv-aura/Scripts/python.exe tests/verify_midi_metrics.py \\
        --midi-dir experiments/aura-midi/eval/runs/eval-antiforget-step25/midi
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import symusic  # noqa: E402


def file_metrics(path: Path) -> dict:
    """Compute metrics independently from symusic."""
    score = symusic.Score(str(path))
    tpq = score.tpq

    all_notes = []
    for tr in score.tracks:
        for n in tr.notes:
            all_notes.append((tr, n))

    total_notes = len(all_notes)

    if total_notes == 0:
        end_tick = 0
        onset_first = onset_last = 0
    else:
        end_tick = max(n.end for _, n in all_notes)
        onset_first = min(n.start for _, n in all_notes)
        onset_last = max(n.start for _, n in all_notes)

    duration_beats = end_tick / tpq if tpq else 0.0

    tempos = score.tempos
    bpm = tempos[0].qpm if tempos else 120.0
    duration_sec = duration_beats * 60.0 / bpm if bpm else 0.0

    note_durs_beats = [(n.end - n.start) / tpq for _, n in all_notes] if all_notes else []
    mean_note_dur_beats = sum(note_durs_beats) / len(note_durs_beats) if note_durs_beats else 0.0

    velocities = [n.velocity for _, n in all_notes] if all_notes else []
    pitches = [n.pitch for _, n in all_notes] if all_notes else []

    density = total_notes / duration_beats if duration_beats else 0.0

    events = []
    for _, n in all_notes:
        events.append((n.start, 1))
        events.append((n.end, -1))
    events.sort()
    cur = 0
    max_poly = 0
    for _, delta in events:
        cur += delta
        if cur > max_poly:
            max_poly = cur

    tracks = []
    for ti, tr in enumerate(score.tracks):
        tracks.append({
            "index": ti,
            "program": tr.program,
            "is_drum": tr.is_drum,
            "name": tr.name,
            "notes": len(tr.notes),
        })

    return {
        "tpq": int(tpq),
        "tempos": [(float(t.time), float(t.qpm)) for t in tempos],
        "tracks": tracks,
        "total_notes": int(total_notes),
        "duration_ticks": int(end_tick),
        "duration_beats": round(duration_beats, 4),
        "duration_sec": round(duration_sec, 4),
        "mean_note_dur_beats": round(mean_note_dur_beats, 4),
        "mean_velocity": round(sum(velocities) / len(velocities), 2) if velocities else 0.0,
        "mean_pitch": round(sum(pitches) / len(pitches), 2) if pitches else 0.0,
        "pitch_min": int(min(pitches)) if pitches else None,
        "pitch_max": int(max(pitches)) if pitches else None,
        "velocity_min": int(min(velocities)) if velocities else None,
        "velocity_max": int(max(velocities)) if velocities else None,
        "max_polyphony": int(max_poly),
        "onset_first_tick": int(onset_first) if total_notes else None,
        "onset_last_tick": int(onset_last) if total_notes else None,
        "density": round(density, 4),
        "valid": True,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--midi-dir", required=True)
    ap.add_argument("--prompts", default=str(REPO_ROOT / "experiments" / "aura-midi" / "eval" / "prompts.json"))
    args = ap.parse_args()

    prompts = json.loads(Path(args.prompts).read_text())["prompts"]
    prompt_source = {p["prompt_id"]: p["source"] for p in prompts}
    prompt_role = {p["prompt_id"]: p["role_hint"] for p in prompts}

    midi_dir = Path(args.midi_dir)
    files = sorted(midi_dir.glob("*.mid"))

    results = []
    for f in files:
        try:
            fm = file_metrics(f)
        except Exception as e:
            fm = {"valid": False, "error": str(e)}
        stem = f.stem
        parts = stem.split("_", 1)
        model = parts[0]
        prompt_id = parts[1] if len(parts) > 1 else ""
        fm.update({
            "model": model,
            "prompt_id": prompt_id,
            "source": prompt_source.get(prompt_id, "unknown"),
            "role_hint": prompt_role.get(prompt_id, "unknown"),
            "midi_path": str(f),
        })
        results.append(fm)

    summary = {}
    for model in ("pretrained", "finetuned"):
        summary[model] = {}
        for source in ("nrgcp", "gmd"):
            gs = [g for g in results if g.get("model") == model and g.get("source") == source and g.get("valid")]
            if not gs:
                continue
            n = len(gs)
            summary[model][source] = {
                "n_prompts": n,
                "le1_note_prompts": sum(1 for g in gs if g["total_notes"] <= 1),
                "zero_note_prompts": sum(1 for g in gs if g["total_notes"] == 0),
                "mean_notes": round(sum(g["total_notes"] for g in gs) / n, 3),
                "mean_duration_beats": round(sum(g["duration_beats"] for g in gs) / n, 3),
                "mean_duration_sec": round(sum(g["duration_sec"] for g in gs) / n, 3),
                "mean_density": round(sum(g["density"] for g in gs) / n, 4),
                "all_valid": all(g["valid"] for g in gs),
            }

    out = {
        "midi_dir": str(midi_dir),
        "n_files": len(files),
        "generations": results,
        "summary": summary,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
