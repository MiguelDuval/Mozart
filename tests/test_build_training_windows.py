#!/usr/bin/env python3
"""Tests for deterministic source-aware training windows."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_training_windows import window_ranges


class TrainingWindowTests(unittest.TestCase):
    def test_short_source_produces_no_window(self) -> None:
        normalized = type(
            "Normalized",
            (),
            {
                "length_beats": 12.0,
                "length_bars": 3,
                "time_signatures": (),
            },
        )()
        self.assertEqual(window_ranges(normalized), [])

    def test_twenty_bars_are_partitioned_into_sixteen_plus_four(self) -> None:
        normalized = type(
            "Normalized",
            (),
            {
                "length_beats": 80.0,
                "length_bars": 20,
                "time_signatures": (),
            },
        )()
        self.assertEqual(
            window_ranges(normalized),
            [
                (0.0, 64.0, 0, 16),
                (64.0, 80.0, 16, 20),
            ],
        )

    def test_eighteen_bars_avoid_a_too_short_tail(self) -> None:
        normalized = type(
            "Normalized",
            (),
            {
                "length_beats": 72.0,
                "length_bars": 18,
                "time_signatures": (),
            },
        )()
        self.assertEqual(
            window_ranges(normalized),
            [
                (0.0, 56.0, 0, 14),
                (56.0, 72.0, 14, 18),
            ],
        )


    def test_build_windows_rebases_notes_and_clips_sustains(self) -> None:
        from build_training_windows import build_windows

        def vlq(value: int) -> bytes:
            parts = [value & 0x7F]
            value >>= 7
            while value:
                parts.append((value & 0x7F) | 0x80)
                value >>= 7
            parts.reverse()
            return bytes(parts)

        events = bytearray()
        for bar in range(20):
            events += vlq(0 if bar == 0 else 1440) + bytes.fromhex("90 3C 64")
            events += vlq(480) + bytes.fromhex("80 3C 00")
        events += bytes.fromhex("00 FF 2F 00")

        header = b"MThd" + bytes.fromhex("00 00 00 06 00 00 00 00 01 E0")
        track = b"MTrk" + len(events).to_bytes(4, "big") + bytes(events)

        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            midi_path = root / "long.mid"
            midi_path.write_bytes(header + track)

            examples = build_windows(
                midi_path,
                source_id="long-source",
                source_revision="rev-1",
                source_path="long.mid",
                seed=10,
            )

        self.assertEqual(len(examples), 2)
        self.assertEqual(
            [(item["window"]["start_bar"], item["window"]["end_bar"]) for item in examples],
            [(0, 16), (16, 20)],
        )
        self.assertEqual(examples[0]["music"]["length_bars"], 16)
        self.assertEqual(examples[1]["music"]["length_bars"], 4)
        self.assertEqual(examples[0]["music"]["length_beats"], 64.0)
        self.assertEqual(examples[1]["music"]["length_beats"], 16.0)
        self.assertEqual(examples[1]["source_id"], "long-source")
        self.assertEqual(examples[1]["conditioning"]["seed"], 11)
        self.assertEqual(examples[1]["tokens"][0], 1)
        self.assertEqual(examples[1]["tokens"][-1], 2)

    def test_sixteen_bars_is_one_window(self) -> None:
        normalized = type(
            "Normalized",
            (),
            {
                "length_beats": 64.0,
                "length_bars": 16,
                "time_signatures": (),
            },
        )()
        self.assertEqual(
            window_ranges(normalized),
            [(0.0, 64.0, 0, 16)],
        )


if __name__ == "__main__":
    unittest.main()
