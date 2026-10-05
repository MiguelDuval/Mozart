#!/usr/bin/env python3
"""Tests for the frozen Mozart conditioning vocabulary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mozart_conditioning import (
    CONDITIONING_VOCABULARY_ID,
    PERFORMANCE_CONTROL_NAMES,
    derive_performance_controls,
    validate_conditioning,
    validate_performance_controls,
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

    def test_performance_controls_are_bounded_and_ordered(self) -> None:
        controls = validate_performance_controls({
            "density": 0.1,
            "energy": 0.2,
            "syncopation": 0.3,
            "swing": 0.4,
            "variation": 0.5,
        })
        self.assertEqual(tuple(controls), tuple(PERFORMANCE_CONTROL_NAMES))
        with self.assertRaises(ValueError):
            validate_performance_controls({
                "density": 1.1,
                "energy": 0.2,
                "syncopation": 0.3,
                "swing": 0.4,
                "variation": 0.5,
            })

    def test_derived_controls_are_deterministic(self) -> None:
        notes = [
            {"start_beat": 0.0, "duration_beats": 0.25, "note": 36, "velocity": 127, "channel": 0},
            {"start_beat": 0.25, "duration_beats": 0.25, "note": 38, "velocity": 64, "channel": 0},
        ]
        result = derive_performance_controls(notes, 1.0)
        self.assertAlmostEqual(result["density"], 0.5)
        self.assertAlmostEqual(result["energy"], 0.7519685039)
        self.assertAlmostEqual(result["syncopation"], 0.5)
        self.assertAlmostEqual(result["swing"], 0.0)
        self.assertAlmostEqual(result["variation"], 0.1428571429)

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
