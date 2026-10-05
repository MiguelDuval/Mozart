#!/usr/bin/env python3
"""Contract tests for the shared Mozart token grammar policy."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mozart_token_grammar import (
    BOS,
    EOS,
    CHANNEL_BASE,
    NOTE_BASE,
    VELOCITY_BASE,
    TIME_SHIFT_BASE,
    DURATION_BASE,
    CONTROLLER_BASE,
    CONTROL_VALUE_BASE,
    VOCABULARY_SIZE,
    allowed_next_token_ranges,
    is_allowed_next_token,
)


class MozartTokenGrammarTests(unittest.TestCase):
    def test_vocabulary_constants_match_frozen_abi(self) -> None:
        self.assertEqual(BOS, 1)
        self.assertEqual(EOS, 2)
        self.assertEqual(CHANNEL_BASE, 16)
        self.assertEqual(NOTE_BASE, 32)
        self.assertEqual(VELOCITY_BASE, 160)
        self.assertEqual(TIME_SHIFT_BASE, 192)
        self.assertEqual(DURATION_BASE, 256)
        self.assertEqual(CONTROLLER_BASE, 352)
        self.assertEqual(CONTROL_VALUE_BASE, 480)
        self.assertEqual(VOCABULARY_SIZE, 512)

    def test_state_ranges_follow_frozen_event_order(self) -> None:
        self.assertEqual(
            allowed_next_token_ranges([BOS]),
            ((CHANNEL_BASE, NOTE_BASE), (TIME_SHIFT_BASE, DURATION_BASE)),
        )
        self.assertEqual(
            allowed_next_token_ranges([BOS, CHANNEL_BASE]),
            ((NOTE_BASE, VELOCITY_BASE), (CONTROLLER_BASE, CONTROL_VALUE_BASE)),
        )
        self.assertEqual(
            allowed_next_token_ranges([BOS, CHANNEL_BASE, NOTE_BASE]),
            ((VELOCITY_BASE, TIME_SHIFT_BASE),),
        )
        self.assertEqual(
            allowed_next_token_ranges([BOS, CHANNEL_BASE, NOTE_BASE, VELOCITY_BASE]),
            ((DURATION_BASE, CONTROLLER_BASE),),
        )
        self.assertEqual(
            allowed_next_token_ranges(
                [BOS, CHANNEL_BASE, NOTE_BASE, VELOCITY_BASE, DURATION_BASE]
            ),
            (
                (EOS, EOS + 1),
                (CHANNEL_BASE, NOTE_BASE),
                (TIME_SHIFT_BASE, DURATION_BASE),
                (NOTE_BASE, VELOCITY_BASE),
                (CONTROLLER_BASE, CONTROL_VALUE_BASE),
            ),
        )

    def test_time_shift_requires_channel_before_direct_event(self) -> None:
        prefix_without_channel = [BOS, TIME_SHIFT_BASE]
        self.assertTrue(is_allowed_next_token(prefix_without_channel, CHANNEL_BASE))
        self.assertTrue(
            is_allowed_next_token(prefix_without_channel, TIME_SHIFT_BASE)
        )
        self.assertFalse(
            is_allowed_next_token(prefix_without_channel, NOTE_BASE)
        )

        prefix_with_channel = [BOS, CHANNEL_BASE, TIME_SHIFT_BASE]
        self.assertTrue(is_allowed_next_token(prefix_with_channel, NOTE_BASE))
        self.assertTrue(
            is_allowed_next_token(prefix_with_channel, CONTROLLER_BASE)
        )

    def test_no_token_is_allowed_after_eos(self) -> None:
        self.assertEqual(allowed_next_token_ranges([EOS]), ())
        for token in (0, BOS, EOS, CHANNEL_BASE, NOTE_BASE, VOCABULARY_SIZE - 1):
            self.assertFalse(is_allowed_next_token([EOS], token))


if __name__ == "__main__":
    unittest.main()
