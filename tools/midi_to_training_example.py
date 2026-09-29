#!/usr/bin/env python3
"""Build deterministic Mozart training examples from normalized MIDI data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from midi_normalize import MidiValidationError, NormalizedMidi, normalize_file
from mozart_tokenizer import VOCABULARY_ID, VOCABULARY_SIZE, encode


def _build_record(
    normalized: NormalizedMidi,
    *,
    source_id: str,
    source_revision: str,
    source_path: str,
    style: str,
    substyle: str,
    mood: str,
    rhythm: str,
    role: str,
    seed: int,
    start_beat: float = 0.0,
    end_beat: float | None = None,
    window_start_bar: int | None = None,
    window_end_bar: int | None = None,
    source_length_bars: int | None = None,
) -> dict:
    source_id = source_id.strip()
    source_revision = source_revision.strip()
    if not source_id:
        raise ValueError("source_id must not be empty")
    if not source_revision:
        raise ValueError("source_revision must not be empty")
    if start_beat < 0.0:
        raise ValueError("start_beat must be non-negative")

    if end_beat is None:
        end_beat = normalized.length_beats
    if end_beat <= start_beat:
        raise ValueError("end_beat must be greater than start_beat")

    notes = []
    for note in normalized.notes:
        if not start_beat <= note.start_beat < end_beat:
            continue
        relative_start = note.start_beat - start_beat
        clipped_end = min(note.start_beat + note.duration_beats, end_beat)
        duration = clipped_end - note.start_beat
        if duration <= 0.0:
            continue
        notes.append(
            {
                "start_beat": relative_start,
                "duration_beats": duration,
                "note": note.note,
                "velocity": note.velocity,
                "channel": note.channel,
            }
        )

    controls = [
        {
            "start_beat": event.start_beat - start_beat,
            "controller": event.controller,
            "value": event.value,
            "channel": event.channel,
        }
        for event in normalized.controls
        if start_beat <= event.start_beat < end_beat
    ]

    if not notes and not controls:
        raise ValueError("training example contains no usable musical events")
    if len(notes) > 4096:
        raise ValueError(
            f"training example exceeds 4096 note events; got {len(notes)}"
        )
    if len(controls) > 1024:
        raise ValueError(
            f"training example exceeds 1024 controller events; got {len(controls)}"
        )

    tokenized = encode(notes, controls)

    polyphony_by_step: dict[int, int] = {}
    pitch_histogram = [0] * 128
    velocity_histogram = [0] * 32
    for note in notes:
        step = round(note["start_beat"] / (1.0 / 16.0))
        polyphony_by_step[step] = polyphony_by_step.get(step, 0) + 1
        pitch_histogram[note["note"]] += 1
        velocity_bin = min(
            32,
            max(1, (note["velocity"] * 32 + 126) // 127),
        )
        velocity_histogram[velocity_bin - 1] += 1

    def rebase_timing_event(event: object) -> dict | None:
        beat = getattr(event, "beat")
        if beat < start_beat:
            return None
        if beat >= end_beat:
            return None
        result = {
            "beat": beat - start_beat,
        }
        for key in ("bpm", "numerator", "denominator"):
            if hasattr(event, key):
                result[key] = getattr(event, key)
        return result

    tempo_events = [
        item
        for item in (
            rebase_timing_event(event) for event in normalized.tempo_events
        )
        if item is not None
    ]
    time_signatures = [
        item
        for item in (
            rebase_timing_event(event)
            for event in normalized.time_signatures
        )
        if item is not None
    ]

    if normalized.time_signatures:
        active_signature = max(
            (
                event
                for event in normalized.time_signatures
                if event.beat <= start_beat
            ),
            key=lambda event: event.beat,
            default=None,
        )
        if active_signature is not None and not any(
            item["beat"] == 0.0 for item in time_signatures
        ):
            time_signatures.insert(
                0,
                {
                    "beat": 0.0,
                    "numerator": active_signature.numerator,
                    "denominator": active_signature.denominator,
                },
            )

    source_length = (
        source_length_bars
        if source_length_bars is not None
        else normalized.length_bars
    )
    record = {
        "schema_version": 1,
        "source_id": source_id,
        "source_revision": source_revision,
        "source_path": source_path,
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
            "length_beats": end_beat - start_beat,
            "length_bars": (
                window_end_bar - window_start_bar
                if window_start_bar is not None and window_end_bar is not None
                else normalized.length_bars
            ),
            "source_length_bars": source_length,
            "note_event_count": len(notes),
            "controller_event_count": len(controls),
            "max_start_step_polyphony": (
                max(polyphony_by_step.values()) if polyphony_by_step else 0
            ),
            "pitch_histogram": pitch_histogram,
            "velocity_bin_histogram": velocity_histogram,
            "tempo_events": tempo_events,
            "time_signatures": time_signatures,
        },
        "tokens": list(tokenized.tokens),
        "diagnostics": {
            "dropped_unmatched_note_offs":
                normalized.dropped_unmatched_note_offs,
            "dropped_unclosed_notes":
                normalized.dropped_unclosed_notes,
        },
    }
    if window_start_bar is not None and window_end_bar is not None:
        record["window"] = {
            "start_bar": window_start_bar,
            "end_bar": window_end_bar,
        }
    return record


def build_example_from_normalized(
    normalized: NormalizedMidi,
    *,
    source_id: str,
    source_revision: str,
    source_path: str,
    style: str = "electronic",
    substyle: str = "generic",
    mood: str = "neutral",
    rhythm: str = "straight",
    role: str = "bass",
    seed: int = 0,
    start_beat: float = 0.0,
    end_beat: float | None = None,
    window_start_bar: int | None = None,
    window_end_bar: int | None = None,
    source_length_bars: int | None = None,
) -> dict:
    if end_beat is None:
        end_beat = normalized.length_beats
    return _build_record(
        normalized,
        source_id=source_id,
        source_revision=source_revision,
        source_path=source_path,
        style=style,
        substyle=substyle,
        mood=mood,
        rhythm=rhythm,
        role=role,
        seed=seed,
        start_beat=start_beat,
        end_beat=end_beat,
        window_start_bar=window_start_bar,
        window_end_bar=window_end_bar,
        source_length_bars=source_length_bars,
    )


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
    if not 4 <= normalized.length_bars <= 16:
        raise ValueError(
            f"training example length must be 4..16 bars; got {normalized.length_bars}"
        )
    return build_example_from_normalized(
        normalized,
        source_id=source_id,
        source_revision=source_revision,
        source_path=source_path or midi_path.as_posix(),
        style=style,
        substyle=substyle,
        mood=mood,
        rhythm=rhythm,
        role=role,
        seed=seed,
    )


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
