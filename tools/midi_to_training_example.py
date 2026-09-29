#!/usr/bin/env python3
"""Build one deterministic Mozart training example from an SMF file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from midi_normalize import normalize_file, MidiValidationError
from mozart_tokenizer import VOCABULARY_ID, VOCABULARY_SIZE, encode


def build_example(
    midi_path: Path,
    *,
    source_id: str,
    source_revision: str,
    source_path: str | None = None,
    style: str = "electronic",
    substyle: str = "generic",
    mood: str = "neutral",
    rhythm: str = "straight",
    role: str = "bass",
    seed: int = 0,
) -> dict:
    normalized = normalize_file(midi_path)

    source_id = source_id.strip()
    source_revision = source_revision.strip()
    if not source_id:
        raise ValueError("source_id must not be empty")
    if not source_revision:
        raise ValueError("source_revision must not be empty")

    if not 4 <= normalized.length_bars <= 16:
        raise ValueError(
            f"training example length must be 4..16 bars; got {normalized.length_bars}"
        )

    if not normalized.notes and not normalized.controls:
        raise ValueError("training example contains no usable musical events")
    if len(normalized.notes) > 4096:
        raise ValueError(
            f"training example exceeds 4096 note events; got {len(normalized.notes)}"
        )
    if len(normalized.controls) > 1024:
        raise ValueError(
            f"training example exceeds 1024 controller events; got {len(normalized.controls)}"
        )

    tokenized = encode(
        [item.__dict__ for item in normalized.notes],
        [item.__dict__ for item in normalized.controls],
    )

    polyphony_by_step: dict[int, int] = {}
    pitch_histogram = [0] * 128
    velocity_histogram = [0] * 32
    for note in normalized.notes:
        step = round(note.start_beat / (1.0 / 16.0))
        polyphony_by_step[step] = polyphony_by_step.get(step, 0) + 1
        pitch_histogram[note.note] += 1
        velocity_bin = min(32, max(1, (note.velocity * 32 + 126) // 127))
        velocity_histogram[velocity_bin - 1] += 1

    return {
        "schema_version": 1,
        "source_id": source_id,
        "source_revision": source_revision,
        "source_path": source_path if source_path is not None else midi_path.as_posix(),
        "vocabulary_id": VOCABULARY_ID,
        "vocabulary_size": VOCABULARY_SIZE,
        "conditioning": {
            "style": style,
            "substyle": substyle,
            "mood": mood,
            "rhythm": rhythm,
            "role": role,
            "seed": seed,
        },
        "source": {
            "format": normalized.source_format,
            "tracks": normalized.source_tracks,
            "division": normalized.source_division,
            "ppq": normalized.ppq,
        },
        "music": {
            "length_beats": normalized.length_beats,
            "length_bars": normalized.length_bars,
            "note_event_count": len(normalized.notes),
            "controller_event_count": len(normalized.controls),
            "max_start_step_polyphony": (
                max(polyphony_by_step.values()) if polyphony_by_step else 0
            ),
            "pitch_histogram": pitch_histogram,
            "velocity_bin_histogram": velocity_histogram,
            "tempo_events": [
                {
                    "beat": event.beat,
                    "bpm": event.bpm,
                }
                for event in normalized.tempo_events
            ],
            "time_signatures": [
                {
                    "beat": event.beat,
                    "numerator": event.numerator,
                    "denominator": event.denominator,
                }
                for event in normalized.time_signatures
            ],
        },
        "tokens": list(tokenized.tokens),
        "diagnostics": {
            "dropped_unmatched_note_offs":
                normalized.dropped_unmatched_note_offs,
            "dropped_unclosed_notes":
                normalized.dropped_unclosed_notes,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("midi_file", type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-path")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--style", default="electronic")
    parser.add_argument("--substyle", default="generic")
    parser.add_argument("--mood", default="neutral")
    parser.add_argument("--rhythm", default="straight")
    parser.add_argument("--role", default="bass")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    try:
        result = build_example(
            args.midi_file,
            source_id=args.source_id,
            source_revision=args.source_revision,
            source_path=args.source_path,
            style=args.style,
            substyle=args.substyle,
            mood=args.mood,
            rhythm=args.rhythm,
            role=args.role,
            seed=args.seed,
        )
    except (MidiValidationError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
        print(f"PASS: wrote Mozart training example to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
