#!/usr/bin/env python3
"""Tests for the Mozart context-diversity A/B training-contract validator."""

from __future__ import annotations

import copy
import sys
import unittest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tools"))

from validate_mozart_conditioning_ab import validate_records


def _record(
    source_id: str,
    source_path: str,
    tokens: list[int],
    density: float,
) -> dict:
    return {
        "source_id": source_id,
        "source_path": source_path,
        "tokens": tokens,
        "performance_controls": {
            "density": density,
            "energy": 0.5,
            "syncopation": 0.5,
            "swing": 0.5,
            "variation": 0.5,
        },
    }


def _dataset() -> tuple[list[dict], list[dict], list[dict]]:
    base = [
        _record(
            f"base-{i}",
            f"midi/control-probe-{i:02d}-v0.mid",
            [10, i, 20],
            0.1 + i * 0.01,
        )
        for i in range(10)
    ]
    diverse = []
    matched = []
    for i, base_record in enumerate(base):
        for variant in (0, 1):
            path = f"midi/control-probe-{i:02d}-v{variant}.mid"
            diverse_tokens = (
                list(base_record["tokens"])
                if variant == 0
                else [10, i, 21]
            )
            diverse.append(
                _record(
                    f"diverse-{i}-{variant}",
                    path,
                    diverse_tokens,
                    base_record["performance_controls"]["density"],
                )
            )
            matched.append(
                _record(
                    f"matched-{i}-{variant}",
                    base_record["source_path"],
                    list(base_record["tokens"]),
                    base_record["performance_controls"]["density"],
                )
            )
    return base, diverse, matched


class MozartConditioningABValidatorTests(unittest.TestCase):
    def test_valid_matched_exposure_layout(self) -> None:
        base, diverse, matched = _dataset()
        result = validate_records(base, diverse, matched)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["diverse_variant_positions"], 10)
        self.assertEqual(result["diverse_base_positions"], 10)

    def test_rejects_target_mismatch_in_matched_baseline(self) -> None:
        base, diverse, matched = _dataset()
        matched[7]["tokens"] = [10, 7, 99]
        with self.assertRaisesRegex(ValueError, "matched\[7\] tokens differ"):
            validate_records(base, diverse, matched)

    def test_rejects_control_mismatch(self) -> None:
        base, diverse, matched = _dataset()
        diverse[3]["performance_controls"]["density"] = 0.99
        with self.assertRaisesRegex(ValueError, "diverse\[3\] controls differ"):
            validate_records(base, diverse, matched)

    def test_rejects_missing_variant_difference(self) -> None:
        base, diverse, matched = _dataset()
        diverse[1]["tokens"] = list(base[0]["tokens"])
        with self.assertRaisesRegex(ValueError, "variant target unexpectedly equals"):
            validate_records(base, diverse, matched)


if __name__ == "__main__":
    unittest.main()
