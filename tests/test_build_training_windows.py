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
