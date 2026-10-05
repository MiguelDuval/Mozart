#!/usr/bin/env python3
"""Tests for held-out conditioning report aggregation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from summarize_mozart_heldout_conditioning import summarize_heldout_contexts


class HeldoutConditioningSummaryTests(unittest.TestCase):
    def _write_reports(
        self,
        root: Path,
        context: str,
        matched: dict,
        diverse: dict,
    ) -> None:
        for arm, payload in (("matched", matched), ("diverse", diverse)):
            (root / arm).mkdir(parents=True, exist_ok=True)
            for suffix in ("teacher", "sequence"):
                (root / arm / f"{context}-{suffix}.json").write_text(
                    json.dumps(payload) + "\n",
                    encoding="utf-8",
                )

    def _teacher_payload(self, value: float) -> dict:
        return {
            "status": "PASS",
            "target_probability_directional_response_rate": value,
            "target_family_probability_directional_response_rate": value + 0.1,
            "mean_target_probability_delta_native_minus_counterfactual": value + 0.2,
            "mean_distribution_total_variation_native_vs_counterfactual": value + 0.3,
        }

    def _sequence_payload(self, value: float) -> dict:
        controls = {}
        changed_controls = int(value)
        for index in range(5):
            controls[f"control-{index}"] = {
                "torch": {
                    "sequence_changed": index < changed_controls,
                    "distribution_response": {
                        "max_total_variation": value + 0.1,
                    },
                }
            }
        return {
            "status": "PASS",
            "controls": controls,
        }

    def test_aggregates_context_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, offset in enumerate((1.0, 2.0)):
                context = f"context-{index:02d}"
                matched = self._teacher_payload(0.5)
                diverse = self._teacher_payload(0.5 + offset)
                for arm, payload in (("matched", matched), ("diverse", diverse)):
                    (root / arm).mkdir(parents=True, exist_ok=True)
                    (root / arm / f"{context}-teacher.json").write_text(
                        json.dumps(payload) + "\n",
                        encoding="utf-8",
                    )
                    seq = self._sequence_payload(1.0)
                    if arm == "diverse":
                        seq = self._sequence_payload(1.0 + offset)
                    (root / arm / f"{context}-sequence.json").write_text(
                        json.dumps(seq) + "\n",
                        encoding="utf-8",
                    )

            summary = summarize_heldout_contexts(
                root / "matched",
                root / "diverse",
                context_count=2,
            )

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["context_count"], 2)
        self.assertAlmostEqual(
            summary["aggregate_diverse_minus_matched"]["teacher_forced"][
                "target_probability_directional_response_rate"
            ]["mean"],
            1.5,
        )
        self.assertAlmostEqual(
            summary["aggregate_diverse_minus_matched"][
                "grammar_constrained_sequence"
            ]["mean_control_max_total_variation"]["sample_stddev"],
            0.70710678118,
            places=8,
        )

    def test_rejects_sequence_report_without_control_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ("matched", "diverse"):
                (root / arm).mkdir(parents=True, exist_ok=True)
                teacher = self._teacher_payload(0.5)
                sequence = {"status": "PASS", "controls": {}}
                (root / arm / "context-00-teacher.json").write_text(
                    json.dumps(teacher) + "\n",
                    encoding="utf-8",
                )
                (root / arm / "context-00-sequence.json").write_text(
                    json.dumps(sequence) + "\n",
                    encoding="utf-8",
                )
            with self.assertRaisesRegex(ValueError, "non-empty object"):
                summarize_heldout_contexts(
                    root / "matched",
                    root / "diverse",
                    context_count=1,
                )

    def test_rejects_failed_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ("matched", "diverse"):
                (root / arm).mkdir(parents=True, exist_ok=True)
                for context in ("context-00",):
                    teacher = self._teacher_payload(0.5)
                    sequence = self._sequence_payload(1.0)
                    if arm == "diverse":
                        teacher["status"] = "FAIL"
                    (root / arm / f"{context}-teacher.json").write_text(
                        json.dumps(teacher) + "\n",
                        encoding="utf-8",
                    )
                    (root / arm / f"{context}-sequence.json").write_text(
                        json.dumps(sequence) + "\n",
                        encoding="utf-8",
                    )
            with self.assertRaisesRegex(ValueError, "not PASS"):
                summarize_heldout_contexts(
                    root / "matched",
                    root / "diverse",
                    context_count=1,
                )
