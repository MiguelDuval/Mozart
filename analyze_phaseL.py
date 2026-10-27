#!/usr/bin/env python3
"""
Phase L root-cause analysis: per-prompt comparison of pretrained / step-25 / step-50
for the 6 GMD drum prompts. Outputs a machine-readable JSON diagnostic report.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import symusic  # noqa: E402

STEP25_MIDI = REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / "eval-antiforget-step25" / "midi"
STEP50_MIDI = REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / "eval-antiforget-step50" / "midi"
OUT = REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / "eval-antiforget-step50" / "phaseL_diagnostic.json"

GMD_PROMPTS = ["gmd-06", "gmd-07", "gmd-08", "gmd-09", "gmd-10", "gmd-11"]


def midi_stats(path: Path) -> dict:
    score = symusic.Score(str(path))
    tpq = score.tpq
    tempos = [(t.time, t.qpm) for t in score.tempos]
    tracks = []
    total_notes = 0
    all_durs = []
    all_vels = []
    all_pitches = []
    all_onsets = []
    max_poly = 0
    end_tick = 0
    for ti, tr in enumerate(score.tracks):
        tinfo = {
            "index": ti,
            "program": tr.program,
            "is_drum": tr.is_drum,
            "name": tr.name,
            "notes": len(tr.notes),
        }
        total_notes += len(tr.notes)
        for n in tr.notes:
            all_durs.append(n.end - n.start)
            all_vels.append(n.velocity)
            all_pitches.append(n.pitch)
            all_onsets.append(n.start)
            if n.end > end_tick:
                end_tick = n.end
        tracks.append(tinfo)
    events = []
    for tr in score.tracks:
        for n in tr.notes:
            events.append((n.start, 1))
            events.append((n.end, -1))
    events.sort()
    cur = 0
    for _, delta in events:
        cur += delta
        if cur > max_poly:
            max_poly = cur
    duration_beats = end_tick / tpq if tpq else 0.0
    bpm = tempos[0][1] if tempos else 120.0
    duration_sec = duration_beats * 60.0 / bpm if bpm else 0.0
    return {
        "tpq": int(tpq),
        "tempos": tempos,
        "tracks": tracks,
        "total_notes": int(total_notes),
        "duration_ticks": int(end_tick),
        "duration_beats": round(duration_beats, 4),
        "duration_sec": round(duration_sec, 4),
        "mean_note_dur_beats": round(sum(all_durs) / len(all_durs) / tpq, 4) if all_durs else 0.0,
        "mean_velocity": round(sum(all_vels) / len(all_vels), 2) if all_vels else 0.0,
        "mean_pitch": round(sum(all_pitches) / len(all_pitches), 2) if all_pitches else 0.0,
        "pitch_min": int(min(all_pitches)) if all_pitches else None,
        "pitch_max": int(max(all_pitches)) if all_pitches else None,
        "velocity_min": int(min(all_vels)) if all_vels else None,
        "velocity_max": int(max(all_vels)) if all_vels else None,
        "max_polyphony": int(max_poly),
        "onset_first_tick": int(min(all_onsets)) if all_onsets else None,
        "onset_last_tick": int(max(all_onsets)) if all_onsets else None,
    }


def main():
    results = {"gmd_prompts": [], "duration_check": {}, "summary": {}}
    for pid in GMD_PROMPTS:
        entry = {"prompt_id": pid, "models": {}}
        for mname, prefix, mdir in (
            ("pretrained", "pretrained", STEP25_MIDI),
            ("step_25", "finetuned", STEP25_MIDI),
            ("step_50", "finetuned", STEP50_MIDI),
        ):
            candidates = sorted(mdir.glob(f"{prefix}_{pid}.mid"))
            if not candidates:
                entry["models"][mname] = {"error": f"no midi file {prefix}_{pid}"}
                continue
            entry["models"][mname] = midi_stats(candidates[0])
        results["gmd_prompts"].append(entry)

    results["duration_check"]["method_note"] = (
        "duration_beats = max(note.end) / tpq over ALL tracks (prompt + continuation). "
        "bpm uses only score.tempos[0].qpm (first tempo). Same definition applied to all models."
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"Wrote {OUT} ({len(GMD_PROMPTS)} prompts)")


if __name__ == "__main__":
    main()