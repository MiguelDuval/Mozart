#!/usr/bin/env python3
"""Tests for the frozen Mozart conditioning vocabulary."""

from __future__ import annotations

import unittest

from mozart_conditioning import (
    CONDITIONING_VOCABULARY_ID,
    validate_conditioning,
)


class MozartConditioningTests(unittest.TestCase):
    def test_known_values_round_trip(self) -> None:
        result = validate_conditioning(
            style=" dark_techno ",
            substyle="dark_techno",
            mood="dark",
            rhythm="straight",
            role="bass",
            seed=123,
        )
        self.assertEqual(result["style"], "dark_techno")
        self.assertEqual(result["substyle"], "dark_techno")
        self.assertEqual(result["seed"], 123)
        self.assertEqual(CONDITIONING_VOCABULARY_ID, "mozart-conditioning-v1")

    def test_unknown_slug_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_conditioning(
                style="not_a_real_style",
                substyle="generic",
                mood="neutral",
                rhythm="straight",
                role="bass",
                seed=0,
            )

    def test_seed_matches_uint32(self) -> None:
        valid = validate_conditioning(
            style="electronic",
            substyle="generic",
            mood="neutral",
            rhythm="straight",
            role="bass",
            seed=0xFFFFFFFF,
        )
        self.assertEqual(valid["seed"], 0xFFFFFFFF)

        with self.assertRaises(ValueError):
            validate_conditioning(
                style="electronic",
                substyle="generic",
                mood="neutral",
                rhythm="straight",
                role="bass",
                seed=-1,
            )

        with self.assertRaises(ValueError):
            validate_conditioning(
                style="electronic",
                substyle="generic",
                mood="neutral",
                rhythm="straight",
                role="bass",
                seed=0x100000000,
            )

    def test_bool_seed_is_not_accepted_as_integer(self) -> None:
        with self.assertRaises(ValueError):
            validate_conditioning(
                style="electronic",
                substyle="generic",
                mood="neutral",
                rhythm="straight",
                role="bass",
                seed=True,
            )


if __name__ == "__main__":
    unittest.main()
