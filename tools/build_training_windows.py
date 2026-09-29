#!/usr/bin/env python3
"""Build deterministic 4–16 bar training windows from normalized Mozart MIDI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from midi_normalize import NormalizedMidi, bar_boundaries, normalize_file
from midi_to_training_example import build_example_from_normalized


def window_ranges(
    normalized: NormalizedMidi,
    *,
    max_bars: int = 16,
    min_bars: int = 4,
) -> list[tuple[float, float, int, int]]:
    if not 1 <= min_bars <= max_bars <= 16:
        raise ValueError(
            "window bars must satisfy 1 <= min_bars <= max_bars <= 16"
        )

    boundaries = bar_boundaries(
        normalized.length_beats,
        list(normalized.time_signatures),
    )
    total_bars = len(boundaries) - 1
    if total_bars < min_bars:
        return []

    ranges: list[tuple[float, float, int, int]] = []
    start_bar = 0
    while start_bar < total_bars:
        remaining = total_bars - start_bar
        if remaining <= max_bars:
            if remaining >= min_bars:
                ranges.append(
                    (
                        boundaries[start_bar],
                        boundaries[total_bars],
                        start_bar,
                        total_bars,
                    )
                )
            break

        end_bar = start_bar + max_bars
        tail_bars = total_bars - end_bar
        if 0 < tail_bars < min_bars:
            end_bar = total_bars - min_bars

        if end_bar - start_bar < min_bars:
            raise ValueError(
                "cannot partition source into windows satisfying the bar bounds"
            )

        ranges.append(
            (
                boundaries[start_bar],
                boundaries[end_bar],
                start_bar,
                end_bar,
            )
        )
        start_bar = end_bar

    return ranges


def build_windows(
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
    max_bars: int = 16,
    min_bars: int = 4,
) -> list[dict]:
    normalized = normalize_file(midi_path)
    output: list[dict] = []

    for index, (start_beat, end_beat, start_bar, end_bar) in enumerate(
        window_ranges(normalized, max_bars=max_bars, min_bars=min_bars)
    ):
        output.append(
            build_example_from_normalized(
                normalized,
                source_id=source_id,
                source_revision=source_revision,
                source_path=source_path or midi_path.as_posix(),
                style=style,
                substyle=substyle,
                mood=mood,
                rhythm=rhythm,
                role=role,
                seed=seed + index,
                start_beat=start_beat,
                end_beat=end_beat,
                window_start_bar=start_bar,
                window_end_bar=end_bar,
                source_length_bars=normalized.length_bars,
            )
        )

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("midi_file", type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--style", default="electronic")
    parser.add_argument("--substyle", default="generic")
    parser.add_argument("--mood", default="neutral")
    parser.add_argument("--rhythm", default="straight")
    parser.add_argument("--role", default="bass")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-bars", type=int, default=4)
    parser.add_argument("--max-bars", type=int, default=16)
    args = parser.parse_args()

    try:
        examples = build_windows(
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
            min_bars=args.min_bars,
            max_bars=args.max_bars,
        )
        payload = "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in examples
        )
        args.output.write_text(payload, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"PASS: wrote {len(examples)} training windows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
