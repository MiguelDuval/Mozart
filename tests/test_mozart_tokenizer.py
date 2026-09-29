#!/usr/bin/env python3
"""Golden and boundary tests for Mozart's Python token encoder."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mozart_tokenizer import (
    BEAT_GRID,
    BOS,
    CONTROL_VALUE_BASE,
    CONTROLLER_BASE,
    DURATION_BASE,
    EOS,
    encode,
)


class MozartTokenizerTests(unittest.TestCase):
    def test_golden_note_and_controller_stream(self) -> None:
        result = encode(
            notes=[
                {
                    "start_beat": 0.0,
                    "duration_beats": 1.0 / 16.0,
                    "note": 60,
                    "velocity": 100,
                    "channel": 0,
                }
            ],
            controls=[
                {
                    "start_beat": 1.5,
                    "controller": 1,
                    "value": 127,
                    "channel": 0,
                }
            ],
        )
        self.assertEqual(
            result.tokens,
            (
                BOS,
                16,
                92,
                216,
                DURATION_BASE,
                215,
                CONTROLLER_BASE + 1,
                CONTROL_VALUE_BASE + 31,
                EOS,
            ),
        )

    def test_same_beat_notes_precede_controls(self) -> None:
        result = encode(
            notes=[
                {
                    "start_beat": 1.0,
                    "duration_beats": BEAT_GRID,
                    "note": 60,
                    "velocity": 127,
                    "channel": 0,
                }
            ],
            controls=[
                {
                    "start_beat": 1.0,
                    "controller": 7,
                    "value": 64,
                    "channel": 0,
                }
            ],
        )
        self.assertEqual(result.tokens[2], 92)
        self.assertEqual(result.tokens[5], CONTROLLER_BASE + 7)

    def test_long_time_shift_is_chunked(self) -> None:
        result = encode(
            notes=[
                {
                    "start_beat": 5.0,
                    "duration_beats": BEAT_GRID,
                    "note": 36,
                    "velocity": 1,
                    "channel": 9,
                }
            ],
            controls=[],
        )
        self.assertEqual(
            result.tokens[1:3],
            (TIME_SHIFT_BASE + 63, TIME_SHIFT_BASE + 15),
        )
        self.assertEqual(result.tokens[3], 16 + 9)
        self.assertEqual(result.tokens[-2], DURATION_BASE)

    def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            encode(
                notes=[
                    {
                        "start_beat": -1.0,
                        "duration_beats": BEAT_GRID,
                        "note": 60,
                        "velocity": 100,
                        "channel": 0,
                    }
                ],
                controls=[],
            )

        with self.assertRaises(ValueError):
            encode(
                notes=[
                    {
                        "start_beat": 0.0,
                        "duration_beats": 0.0,
                        "note": 60,
                        "velocity": 100,
                        "channel": 0,
                    }
                ],
                controls=[],
            )

    def test_token_budget_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            encode(
                notes=[
                    {
                        "start_beat": 0.0,
                        "duration_beats": BEAT_GRID,
                        "note": 60,
                        "velocity": 100,
                        "channel": 0,
                    }
                ],
                controls=[],
                max_tokens=4,
            )


if __name__ == "__main__":
    unittest.main()
