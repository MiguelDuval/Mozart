#!/usr/bin/env python3
"""Tests for the context-diversity A/B summary tool."""

from __future__ import annotations

import sys
import unittest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tools"))

from summarize_mozart_conditioning_ab import (
    build_summary,
    compare_experiments,
    summarize_sequence,
    summarize_teacher,
)


def teacher_report(
    *,
    status: str = "PASS",
    rate: float = 0.5,
    family_rate: float = 0.6,
    target_delta: float = 0.1,
    family_delta: float = 0.2,
    tv: float = 0.3,
) -> dict:
    return {
        "status": status,
        "observed_teacher_forced_steps": 20,
        "native_target_top1_steps": 12,
        "native_legal_target_top1_steps": 15,
        "controls_with_both_legal_targets_top1": 3,
        "controls_with_bidirectional_target_response": 2,
        "target_probability_directional_response_rate": rate,
        "target_family_probability_directional_response_rate": family_rate,
        "mean_target_probability_delta_native_minus_counterfactual": target_delta,
        "mean_target_family_probability_delta_native_minus_counterfactual": family_delta,
        "mean_target_probability_tv_alignment": tv,
        "mean_distribution_total_variation_native_vs_counterfactual": tv + 0.1,
    }


def sequence_report(
    *,
    status: str = "PASS",
    first_changed: bool = True,
    second_changed: bool = False,
    first_tv: float = 0.4,
    second_tv: float = 0.2,
) -> dict:
    return {
        "status": status,
        "grammar_constrained": True,
        "require_valid_grammar": True,
        "require_distribution_response": True,
        "min_distribution_total_variation": 0.05,
        "max_generated_tokens": 32,
        "failures": [],
        "controls": {
            "density": {
                "torch": {
                    "sequence_changed": first_changed,
                    "distribution_response": {
                        "max_total_variation": first_tv,
                        "mean_total_variation": first_tv / 2.0,
                    },
                }
            },
            "energy": {
                "torch": {
                    "sequence_changed": second_changed,
                    "distribution_response": {
                        "max_total_variation": second_tv,
                        "mean_total_variation": second_tv / 2.0,
                    },
                }
            },
        },
    }


def teacher_control(
    *,
    rate: float = 0.5,
    family_rate: float = 0.6,
    target_delta: float = 0.1,
    family_delta: float = 0.2,
    mean_tv: float = 0.3,
    max_tv: float = 0.4,
) -> dict:
    return {
        "target_probability_directional_response_rate": rate,
        "target_family_probability_directional_response_rate": family_rate,
        "mean_target_probability_delta_native_minus_counterfactual": target_delta,
        "mean_target_family_probability_delta_native_minus_counterfactual": family_delta,
        "mean_distribution_total_variation_native_vs_counterfactual": mean_tv,
        "max_distribution_total_variation_native_vs_counterfactual": max_tv,
        "native_target_top1_count": 3,
        "native_legal_target_top1_count": 4,
        "window_step_count": 8,
        "control_effect": {
            "low_target_probability_lift_native_minus_counterfactual": target_delta,
            "high_target_probability_lift_native_minus_counterfactual": target_delta,
            "low_target_directionally_correct": target_delta > 0.0,
            "high_target_directionally_correct": target_delta > 0.0,
            "low_target_top1": True,
            "high_target_top1": True,
        },
    }


def teacher_report_with_controls(
    *,
    density: dict | None = None,
    energy: dict | None = None,
) -> dict:
    report = teacher_report()
    report["controls"] = {
        "density": density or teacher_control(),
        "energy": energy or teacher_control(target_delta=0.2),
        "syncopation": teacher_control(),
        "swing": teacher_control(),
        "variation": teacher_control(),
    }
    return report



class MozartConditioningABSummaryTests(unittest.TestCase):
    def test_teacher_summary_keeps_semantic_metrics(self) -> None:
        report = summarize_teacher(teacher_report())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["observed_teacher_forced_steps"], 20)
        self.assertEqual(
            report["target_probability_directional_response_rate"],
            0.5,
        )
        self.assertEqual(
            report["mean_distribution_total_variation_native_vs_counterfactual"],
            0.4,
        )

    def test_sequence_summary_aggregates_control_signals(self) -> None:
        report = summarize_sequence(sequence_report())
        self.assertEqual(report["controls_with_sequence_change"], 1)
        self.assertAlmostEqual(report["mean_control_max_total_variation"], 0.3)
        self.assertAlmostEqual(report["min_control_max_total_variation"], 0.2)
        self.assertAlmostEqual(report["max_control_max_total_variation"], 0.4)

    def test_per_control_delta_is_diverse_minus_matched(self) -> None:
        matched = sequence_report(first_changed=False, second_changed=False, first_tv=0.2)
        diverse = sequence_report(first_changed=True, second_changed=True, first_tv=0.5)
        comparison = compare_experiments(matched, diverse)
        self.assertEqual(comparison["density"]["sequence_changed_delta"], 1)
        self.assertAlmostEqual(
            comparison["density"]["max_total_variation_delta"],
            0.3,
        )
        self.assertEqual(comparison["energy"]["sequence_changed_delta"], 1)

    def test_build_summary_passes_with_complete_input_contract(self) -> None:
        summary = build_summary(
            input_contract={
                "status": "PASS",
                "fixture_revision": "mozart-conditioning-fixture-v1",
                "input_fingerprint": {
                    "base_train_sha256": "base",
                    "diverse_train_sha256": "diverse",
                    "matched_train_sha256": "matched",
                    "diverse_probe_sha256": "diverse-probe",
                    "matched_probe_sha256": "matched-probe",
                },
                "probe_equivalence": {"status": "PASS"},
            },
            baseline_fit={"train_loss": 1.0, "validation_loss": 2.0},
            matched_fit={"train_loss": 0.8, "validation_loss": 2.1},
            diverse_fit={"train_loss": 0.7, "validation_loss": 2.0},
            baseline_teacher=teacher_report(),
            matched_teacher=teacher_report(),
            diverse_teacher=teacher_report(),
            baseline_sequence=sequence_report(),
            matched_sequence=sequence_report(),
            diverse_sequence=sequence_report(),
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["input_contract"]["probe_equivalence"]["status"], "PASS")
        self.assertIsNotNone(summary["diverse_minus_matched"]["fit"]["train_loss_delta"])

    def test_build_summary_includes_optional_cross_context_v1_sequence_reports(self) -> None:
        summary = build_summary(
            input_contract={
                "status": "PASS",
                "probe_equivalence": {"status": "PASS"},
            },
            baseline_fit=None,
            matched_fit=None,
            diverse_fit=None,
            baseline_teacher=None,
            matched_teacher=teacher_report(),
            diverse_teacher=teacher_report(),
            baseline_sequence=None,
            matched_sequence=sequence_report(),
            diverse_sequence=sequence_report(),
            matched_sequence_v1=sequence_report(first_changed=False, first_tv=0.1, second_tv=0.1),
            diverse_sequence_v1=sequence_report(first_changed=True, first_tv=0.5, second_tv=0.4),
            matched_teacher_v1=teacher_report(rate=0.55, family_rate=0.65, target_delta=0.11, family_delta=0.21, tv=0.31),
            diverse_teacher_v1=teacher_report(rate=0.7, family_rate=0.75, target_delta=0.16, family_delta=0.27, tv=0.29),
        )
        v1 = summary["diverse_minus_matched"]["cross_context_v1"]
        self.assertIsNotNone(v1["teacher_forced"]["matched"])
        self.assertIsNotNone(v1["teacher_forced"]["diverse"])
        self.assertAlmostEqual(
            v1["teacher_forced"]["diverse_minus_matched"]["target_probability_directional_response_rate_delta"],
            0.15,
        )
        self.assertAlmostEqual(
            v1["teacher_forced"]["diverse_minus_matched"]["mean_distribution_total_variation_delta"],
            -0.02,
        )
        self.assertIsNotNone(v1["sequence"]["matched"])
        self.assertIsNotNone(v1["sequence"]["diverse"])
        self.assertEqual(
            v1["sequence"]["per_control_autoregressive"]["density"]["sequence_changed_delta"],
            1,
        )
        self.assertAlmostEqual(
            v1["sequence"]["per_control_autoregressive"]["density"]["max_total_variation_delta"],
            0.4,
        )

    def test_cross_context_summary_pairs_per_control_teacher_and_autoregressive_evidence(self) -> None:
        matched_teacher_v1 = teacher_report_with_controls(
            density=teacher_control(rate=0.45, mean_tv=0.20, max_tv=0.30)
        )
        diverse_teacher_v1 = teacher_report_with_controls(
            density=teacher_control(rate=0.70, mean_tv=0.25, max_tv=0.50)
        )
        matched_sequence_v1 = sequence_report(first_changed=False, first_tv=0.10)
        diverse_sequence_v1 = sequence_report(first_changed=True, first_tv=0.35)

        summary = build_summary(
            input_contract={"status": "PASS", "probe_equivalence": {"status": "PASS"}},
            baseline_fit=None,
            matched_fit=None,
            diverse_fit=None,
            baseline_teacher=None,
            matched_teacher=None,
            diverse_teacher=None,
            baseline_sequence=None,
            matched_sequence=None,
            diverse_sequence=None,
            matched_sequence_v1=matched_sequence_v1,
            diverse_sequence_v1=diverse_sequence_v1,
            matched_teacher_v1=matched_teacher_v1,
            diverse_teacher_v1=diverse_teacher_v1,
        )

        v1 = summary["diverse_minus_matched"]["cross_context_v1"]
        self.assertAlmostEqual(
            v1["teacher_forced_per_control"]["matched"]["density"][
                "target_probability_directional_response_rate"
            ],
            0.45,
        )
        self.assertAlmostEqual(
            v1["teacher_forced_per_control"]["diverse_minus_matched"]["density"][
                "target_probability_directional_response_rate"
            ],
            0.25,
        )
        density = v1["conditioning_retention"]["density"]
        self.assertEqual(
            density["matched"]["autoregressive"]["sequence_changed"],
            False,
        )
        self.assertEqual(
            density["diverse"]["autoregressive"]["sequence_changed"],
            True,
        )
        self.assertAlmostEqual(
            density["diverse"]["autoregressive"]["max_total_variation"],
            0.35,
        )
        self.assertAlmostEqual(
            density["diverse"]["teacher_forced"][
                "mean_distribution_total_variation_native_vs_counterfactual"
            ],
            0.25,
        )


    def test_build_summary_reports_partial_when_required_artifact_is_missing(self) -> None:
        summary = build_summary(
            input_contract={
                "status": "PASS",
                "fixture_revision": "mozart-conditioning-fixture-v1",
                "input_fingerprint": {
                    "diverse_train_sha256": "diverse",
                    "matched_train_sha256": "matched",
                },
                "probe_equivalence": {"status": "PASS"},
            },
            baseline_fit=None,
            matched_fit=None,
            diverse_fit=None,
            baseline_teacher=teacher_report(),
            matched_teacher=teacher_report(),
            diverse_teacher=None,
            baseline_sequence=sequence_report(),
            matched_sequence=sequence_report(),
            diverse_sequence=None,
        )
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertEqual(
            summary["input_contract"]["input_fingerprint"]["diverse_train_sha256"],
            "diverse",
        )
        self.assertIn(
            "context_diverse_teacher_forced",
            summary["missing_required_reports"],
        )
        self.assertIn(
            "context_diverse_sequence",
            summary["missing_required_reports"],
        )

    def test_build_summary_marks_failed_input_contract(self) -> None:
        summary = build_summary(
            input_contract={"status": "FAIL"},
            baseline_fit=None,
            matched_fit=None,
            diverse_fit=None,
            baseline_teacher=teacher_report(),
            matched_teacher=teacher_report(),
            diverse_teacher=teacher_report(),
            baseline_sequence=sequence_report(),
            matched_sequence=sequence_report(),
            diverse_sequence=sequence_report(),
        )
        self.assertEqual(summary["status"], "FAIL")

    def test_build_summary_rejects_incomplete_input_contract(self) -> None:
        summary = build_summary(
            input_contract={"status": "PASS"},
            baseline_fit=None,
            matched_fit=None,
            diverse_fit=None,
            baseline_teacher=teacher_report(),
            matched_teacher=teacher_report(),
            diverse_teacher=teacher_report(),
            baseline_sequence=sequence_report(),
            matched_sequence=sequence_report(),
            diverse_sequence=sequence_report(),
        )
        self.assertEqual(summary["status"], "FAIL")

    def test_build_summary_is_partial_without_input_contract(self) -> None:
        summary = build_summary(
            input_contract=None,
            baseline_fit=None,
            matched_fit=None,
            diverse_fit=None,
            baseline_teacher=teacher_report(),
            matched_teacher=teacher_report(),
            diverse_teacher=teacher_report(),
            baseline_sequence=sequence_report(),
            matched_sequence=sequence_report(),
            diverse_sequence=sequence_report(),
        )
        self.assertEqual(summary["status"], "PARTIAL")

    def test_build_summary_marks_failed_diagnostic_without_becoming_production_gate(self) -> None:
        summary = build_summary(
            baseline_fit=None,
            matched_fit=None,
            diverse_fit=None,
            baseline_teacher=teacher_report(),
            matched_teacher=teacher_report(status="FAIL"),
            diverse_teacher=teacher_report(),
            baseline_sequence=sequence_report(),
            matched_sequence=sequence_report(),
            diverse_sequence=sequence_report(),
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(
            summary["baseline_matched_exposure"]["teacher_forced"]["status"],
            "FAIL",
        )


if __name__ == "__main__":
    unittest.main()
