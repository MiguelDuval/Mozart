#!/usr/bin/env python3
"""Unit tests for conditioning dose-response aggregation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from summarize_mozart_conditioning_dose_response import summarize


def _control(multiplier: float) -> dict:
    return {
        "target_response": {
            "slope_around_neutral": multiplier,
            "monotonic_nondecreasing_fraction": 0.5,
            "integrated_absolute_response": multiplier * 2.0,
        },
        "target_family_response": {
            "slope_around_neutral": multiplier * 3.0,
            "monotonic_nondecreasing_fraction": 1.0,
            "integrated_absolute_response": multiplier * 4.0,
        },
        "distribution_response": {
            "integrated_tv_from_neutral": multiplier * 5.0,
            "max_tv_from_neutral": multiplier * 6.0,
        },
        "rows": [],
    }


class DoseResponseSummaryTests(unittest.TestCase):
    def test_computes_diverse_minus_matched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for seed, delta in ((7, 1.0), (42, 2.0), (123, 3.0)):
                controls = {name: _control(float(seed)) for name in (
                    "density", "energy", "syncopation", "swing", "variation"
                )}
                payload = {
                    "status": "PASS",
                    "levels": [0.1, 0.3, 0.5, 0.7, 0.9],
                    "matched": {"controls": controls},
                    "diverse": {
                        "controls": {
                            name: _control(float(seed) + delta)
                            for name in controls
                        }
                    },
                }
                (root / f"dose-response-seed-{seed}.json").write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )
            result = summarize(root)

        metric = result["controls"]["density"]["target_response.slope_around_neutral"]
        self.assertAlmostEqual(metric["diverse_minus_matched"]["mean"], 2.0)
        self.assertAlmostEqual(metric["diverse_minus_matched"]["sample_stddev"], 0.0)


if __name__ == "__main__":
    unittest.main()
