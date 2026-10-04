#!/usr/bin/env python3
"""Unit tests for the conditioning dose-response evaluator."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from evaluate_mozart_conditioning_dose_response import (
    _monotonic_fraction,
    _parse_levels,
    _slope_around_neutral,
    _trapz_mean_absolute,
)


class DoseResponseHelperTests(unittest.TestCase):
    def test_default_levels_are_valid_and_symmetric(self) -> None:
        levels = _parse_levels("0.1,0.3,0.5,0.7,0.9")
        self.assertEqual(levels, (0.1, 0.3, 0.5, 0.7, 0.9))
        self.assertAlmostEqual(
            _slope_around_neutral(
                dict(zip(levels, (-0.4, -0.2, 0.0, 0.2, 0.4))),
                levels,
            ),
            1.0,
        )

    def test_rejects_unsorted_duplicate_or_missing_neutral_levels(self) -> None:
        for value in (
            "0.1,0.5,0.3",
            "0.1,0.3,0.5,0.5,0.9",
            "0.1,0.3,0.7,0.9",
        ):
            with self.assertRaises(ValueError):
                _parse_levels(value)

    def test_monotonic_fraction(self) -> None:
        self.assertEqual(_monotonic_fraction([-1.0, -0.5, 0.0, 0.2]), 1.0)
        self.assertAlmostEqual(_monotonic_fraction([-1.0, -0.5, -0.6, 0.2]), 2.0 / 3.0)
        self.assertEqual(_monotonic_fraction([1.0, 0.5, 0.0], nondecreasing=False), 1.0)

    def test_integrated_absolute_response(self) -> None:
        values = [0.0, 0.5, 0.0]
        levels = (0.0, 0.5, 1.0)
        self.assertAlmostEqual(_trapz_mean_absolute(values, levels), 0.25)


if __name__ == "__main__":
    unittest.main()
