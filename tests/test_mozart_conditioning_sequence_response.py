#!/usr/bin/env python3
"""TDD contract for autoregressive conditioning responsiveness."""

from __future__ import annotations

import sys
import unittest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))


class FakeGreedyModel:
    """Small deterministic stand-in for the sequence evaluator contract."""

    def __init__(self, responsive: bool) -> None:
        self.responsive = responsive

    def __call__(
        self,
        input_ids,
        style_id,
        substyle_id,
        mood_id,
        rhythm_id,
        role_id,
        performance_controls,
    ):
        import torch

        batch, sequence = input_ids.shape
        logits = torch.full((batch, sequence, 512), -1000.0)
        active = (
            int(torch.argmax(performance_controls, dim=1)[0])
            if torch.any(performance_controls > 0)
            else -1
        )

        if self.responsive and active >= 0:
            token = 32 + active
        else:
            token = 40

        logits[:, -1, token] = 100.0
        return logits


class MozartConditioningSequenceTests(unittest.TestCase):
    def test_sequence_comparison_detects_first_divergence(self) -> None:
        from evaluate_mozart_conditioning_sequence import compare_token_sequences

        report = compare_token_sequences(
            [1, 16, 92, 40, 2],
            [1, 16, 92, 42, 2],
        )

        self.assertTrue(report["sequence_changed"])
        self.assertEqual(report["common_prefix_length"], 3)
        self.assertEqual(report["first_divergence_index"], 3)
        self.assertEqual(report["differing_token_count"], 1)
        self.assertEqual(
            report["differing_positions"],
            [{"index": 3, "low_token": 40, "high_token": 42}],
        )

    def test_responsive_model_passes_strict_gate(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            evaluate_sequence_responsiveness,
        )

        report = evaluate_sequence_responsiveness(
            FakeGreedyModel(responsive=True),
            max_generated_tokens=6,
            prefix_tokens=(1, 16, 92),
            require_divergence=True,
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["failures"], [])
        for name in (
            "density",
            "energy",
            "syncopation",
            "swing",
            "variation",
        ):
            torch_report = report["controls"][name]["torch"]
            self.assertTrue(torch_report["sequence_changed"])
            self.assertIsNotNone(torch_report["first_divergence_index"])
            self.assertGreater(torch_report["differing_token_count"], 0)

    def test_unresponsive_model_fails_strict_gate(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            evaluate_sequence_responsiveness,
        )

        report = evaluate_sequence_responsiveness(
            FakeGreedyModel(responsive=False),
            max_generated_tokens=6,
            prefix_tokens=(1, 16, 92),
            require_divergence=True,
        )

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(len(report["failures"]), 5)
        self.assertIn(
            "conditioning control density did not change the greedy generated token sequence",
            report["failures"],
        )

    def test_non_strict_mode_can_report_without_failing(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            evaluate_sequence_responsiveness,
        )

        report = evaluate_sequence_responsiveness(
            FakeGreedyModel(responsive=False),
            max_generated_tokens=6,
            prefix_tokens=(1, 16, 92),
            require_divergence=False,
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["failures"], [])
        self.assertFalse(
            report["controls"]["variation"]["torch"]["sequence_changed"]
        )


if __name__ == "__main__":
    unittest.main()
