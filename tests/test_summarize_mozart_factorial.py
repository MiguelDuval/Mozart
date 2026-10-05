#!/usr/bin/env python3
"""Tests for 2x2 target/conditioning factorial aggregation."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from summarize_mozart_factorial import summarize_factorial


def _arm_payload(delta: float) -> dict:
    return {
        "status": "PASS",
        "diverse_minus_matched": {
            "fit": {
                "validation_loss_delta": delta,
            },
            "teacher_forced": {
                "target_probability_directional_response_rate_delta": delta,
                "target_family_probability_directional_response_rate_delta": delta,
                "mean_target_probability_delta_delta": delta,
                "mean_distribution_total_variation_delta": delta,
            },
            "grammar_constrained_sequence": {
                "controls_with_sequence_change_delta": delta,
                "mean_control_max_total_variation_delta": delta,
            },
        },
    }


def _heldout_arm_payload(delta: float) -> dict:
    return {
        "status": "PASS",
        "aggregate_diverse_minus_matched": {
            "teacher_forced": {
                "target_probability_directional_response_rate": {"mean": delta},
                "target_family_probability_directional_response_rate": {"mean": delta},
                "mean_target_probability_delta_native_minus_counterfactual": {
                    "mean": delta
                },
                "mean_distribution_total_variation_native_vs_counterfactual": {
                    "mean": delta
                },
            },
            "grammar_constrained_sequence": {
                "controls_with_sequence_change": {"mean": delta},
                "mean_control_max_total_variation": {"mean": delta},
            },
        },
    }


class FactorialSummaryTests(unittest.TestCase):
    def test_computes_main_effects_and_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for seed in (7, 42, 123):
                target = 1.0
                conditioning = 2.0
                joint = 6.0
                payload = {
                    "status": "PASS",
                    "replication_seed": seed,
                    "target_only_context_control": _arm_payload(target),
                    "conditioning_context_control": _arm_payload(conditioning),
                    "joint_context_control": _arm_payload(joint),
                    "heldout_target_only_context_control": _heldout_arm_payload(target),
                    "heldout_conditioning_context_control": _heldout_arm_payload(conditioning),
                    "heldout_joint_context_control": _heldout_arm_payload(joint),
                }
                (root / f"ml-context-diversity-summary-seed-{seed}.json").write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )

            summary = summarize_factorial(root)

        self.assertEqual(summary["status"], "PASS")
        metric = summary["metrics"]["validation_loss"]
        self.assertEqual(metric["target_main_effect"]["mean"], 1.0)
        self.assertEqual(metric["conditioning_main_effect"]["mean"], 2.0)
        self.assertEqual(metric["joint_total_effect"]["mean"], 6.0)
        self.assertEqual(metric["target_x_conditioning_interaction"]["mean"], 3.0)
        self.assertEqual(
            summary["definition"]["target_x_conditioning_interaction"],
            "joint - target-only - conditioning-only + matched",
        )

    def test_requires_all_three_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for seed in (7, 42):
                payload = {
                    "status": "PASS",
                    "replication_seed": seed,
                    "target_only_context_control": _arm_payload(1.0),
                    "conditioning_context_control": _arm_payload(1.0),
                    "joint_context_control": _arm_payload(1.0),
                    "heldout_target_only_context_control": _heldout_arm_payload(1.0),
                    "heldout_conditioning_context_control": _heldout_arm_payload(1.0),
                    "heldout_joint_context_control": _heldout_arm_payload(1.0),
                }
                (root / f"ml-context-diversity-summary-seed-{seed}.json").write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "missing required seed summary"):
                summarize_factorial(root)


if __name__ == "__main__":
    unittest.main()
