#!/usr/bin/env python3
"""Tests for teacher-forced conditioning target diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from evaluate_mozart_conditioning_teacher_forced import (
    _load_records,
    _measure,
    _target_rank,
    _evaluate_with_model,
)


CONTROL_NAMES = (
    "density",
    "energy",
    "syncopation",
    "swing",
    "variation",
)


class FakeTeacherForcedModel:
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
        logits = torch.full(
            (batch, sequence, 512),
            0.0,
            dtype=torch.float32,
        )
        for row in range(batch):
            values = performance_controls[row].tolist()
            index = next(
                index
                for index, value in enumerate(values)
                if abs(value - 0.1) < 1.0e-5
                or abs(value - 0.9) < 1.0e-5
            )
            high = values[index] > 0.5

            if sequence == 3:
                # The divergence target is a valid velocity token. Native
                # controls make their own low/high target the legal top-1.
                token = 170 + index * 2 + int(high)
                logits[row, -1, token] = 100.0
            else:
                # Keep the native target as the legal top-1 and the
                # counterfactual on the opposite token.
                logits[row, :, :] = 1.0 if high else 0.0
                low_context = int(input_ids[row, -1].item()) % 2 == 0
                if low_context:
                    winner = 260 if not high else 261
                else:
                    winner = 260 if high else 261
                logits[row, -1, winner] = 11.0
        return logits


class ReverseDirectionalTeacherForcedModel(FakeTeacherForcedModel):
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
        logits = super().__call__(
            input_ids,
            style_id,
            substyle_id,
            mood_id,
            rhythm_id,
            role_id,
            performance_controls,
        )
        if input_ids.shape[1] == 3:
            import torch

            for row in range(input_ids.shape[0]):
                values = performance_controls[row].tolist()
                index = next(
                    index
                    for index, value in enumerate(values)
                    if abs(value - 0.1) < 1.0e-5
                    or abs(value - 0.9) < 1.0e-5
                )
                high = values[index] > 0.5
                native_token = 170 + index * 2 + int(high)
                reverse_token = 170 + index * 2 + int(not high)
                logits[row, -1, native_token] = 0.0
                logits[row, -1, reverse_token] = 100.0
        return logits


class TeacherForcedTests(unittest.TestCase):
    def test_target_rank_and_margin(self) -> None:
        import numpy as np

        logits = np.full(512, -10.0, dtype=np.float32)
        logits[42] = 7.0
        logits[17] = 4.0
        report = _measure(logits, 42)
        self.assertEqual(_target_rank(logits, 42), 1)
        self.assertTrue(report["target_top1"])
        self.assertEqual(report["target_rank"], 1)
        self.assertEqual(report["top1_token"], 42)
        self.assertEqual(report["target_top1_margin"], 0.0)

    def test_measure_reports_legal_target_probability_and_rank(self) -> None:
        import numpy as np

        logits = np.full(512, -10.0, dtype=np.float32)
        logits[170] = 7.0
        report = _measure(
            logits,
            170,
            context=[1, 16, 68],
        )

        self.assertEqual(report["target_legal_rank"], 1)
        self.assertTrue(report["target_legal_top1"])
        self.assertGreater(report["target_probability"], 0.99)

    def test_counterfactual_window_isolates_control_effect(self) -> None:
        records = {}
        probes = {"controls": {}}

        for index, name in enumerate(CONTROL_NAMES):
            low_id = f"{name}-low"
            high_id = f"{name}-high"
            low_tokens = [1, 16, 68, 170 + index * 2, 260, 192, 2]
            high_tokens = [1, 16, 68, 171 + index * 2, 260, 192, 2]
            records[low_id] = {
                "source_id": low_id,
                "split": "train",
                "tokens": low_tokens,
                "performance_controls": {
                    control: (0.1 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            records[high_id] = {
                "source_id": high_id,
                "split": "train",
                "tokens": high_tokens,
                "performance_controls": {
                    control: (0.9 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            probes["controls"][name] = {
                "prefix_tokens": [1, 16, 68],
                "prefix_length": 3,
                "first_target_divergence_index": 3,
                "low_profile": records[low_id]["performance_controls"],
                "high_profile": records[high_id]["performance_controls"],
                "low_record_source_id": low_id,
                "high_record_source_id": high_id,
            }

        report = _evaluate_with_model(
            FakeTeacherForcedModel(),
            records,
            probes,
            window_size=2,
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["observed_teacher_forced_steps"], 20)
        self.assertEqual(
            report["target_probability_directionally_correct_steps"],
            20,
        )
        self.assertEqual(
            report["target_probability_directional_response_rate"],
            1.0,
        )
        for name in CONTROL_NAMES:
            entry = report["controls"][name]
            self.assertEqual(entry["window_step_count"], 4)
            self.assertEqual(
                entry["top1_changed_by_control_steps"],
                4,
            )
            self.assertEqual(
                entry["target_probability_directionally_correct_steps"],
                4,
            )
            self.assertEqual(
                entry["target_probability_directional_response_rate"],
                1.0,
            )
            self.assertGreater(
                entry["mean_target_probability_tv_alignment"],
                0.0,
            )
            deltas = [
                step["target_logit_delta_native_minus_counterfactual"]
                for step in entry["steps"]
            ]
            self.assertTrue(all(delta != 0.0 for delta in deltas))
            probability_deltas = [
                step["target_probability_delta_native_minus_counterfactual"]
                for step in entry["steps"]
            ]
            self.assertTrue(all(delta > 0.0 for delta in probability_deltas))
            tvs = [
                step["distribution_total_variation_native_vs_counterfactual"]
                for step in entry["steps"]
            ]
            self.assertGreater(
                max(tvs),
                0.0,
            )
            self.assertGreater(
                entry["max_distribution_total_variation_native_vs_counterfactual"],
                0.0,
            )

    def test_tv_response_does_not_imply_directionally_correct_target(self) -> None:
        records = {}
        probes = {"controls": {}}

        for index, name in enumerate(CONTROL_NAMES):
            low_id = f"{name}-low"
            high_id = f"{name}-high"
            records[low_id] = {
                "source_id": low_id,
                "split": "train",
                "tokens": [1, 16, 68, 170 + index * 2, 260],
                "performance_controls": {
                    control: (0.1 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            records[high_id] = {
                "source_id": high_id,
                "split": "train",
                "tokens": [1, 16, 68, 171 + index * 2, 260],
                "performance_controls": {
                    control: (0.9 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            probes["controls"][name] = {
                "prefix_tokens": [1, 16, 68],
                "prefix_length": 3,
                "first_target_divergence_index": 3,
                "low_profile": records[low_id]["performance_controls"],
                "high_profile": records[high_id]["performance_controls"],
                "low_record_source_id": low_id,
                "high_record_source_id": high_id,
            }

        report = _evaluate_with_model(
            ReverseDirectionalTeacherForcedModel(),
            records,
            probes,
            window_size=1,
        )

        self.assertEqual(report["status"], "PASS")
        self.assertGreater(
            report["max_distribution_total_variation_native_vs_counterfactual"],
            0.5,
        )
        self.assertEqual(
            report["target_probability_directional_response_rate"],
            0.0,
        )
        self.assertEqual(
            report["controls_with_bidirectional_target_response"],
            0,
        )


    def test_illegal_teacher_forced_target_is_rejected(self) -> None:
        records = {}
        probes = {"controls": {}}

        for index, name in enumerate(CONTROL_NAMES):
            low_id = f"{name}-low"
            high_id = f"{name}-high"
            low_target = 100 if name == "density" else 170 + index * 2
            high_target = 171 + index * 2
            records[low_id] = {
                "source_id": low_id,
                "split": "train",
                "tokens": [1, 16, 68, low_target, 260],
                "performance_controls": {
                    control: (0.1 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            records[high_id] = {
                "source_id": high_id,
                "split": "train",
                "tokens": [1, 16, 68, high_target, 260],
                "performance_controls": {
                    control: (0.9 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            probes["controls"][name] = {
                "prefix_tokens": [1, 16, 68],
                "prefix_length": 3,
                "first_target_divergence_index": 3,
                "low_profile": records[low_id]["performance_controls"],
                "high_profile": records[high_id]["performance_controls"],
                "low_record_source_id": low_id,
                "high_record_source_id": high_id,
            }

        with self.assertRaisesRegex(ValueError, "target token 100 is not legal"):
            _evaluate_with_model(
                FakeTeacherForcedModel(),
                records,
                probes,
                window_size=1,
            )

    def test_load_records_rejects_duplicate_source_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            record = {
                "source_id": "same",
                "tokens": [1, 16, 68, 160, 258, 2],
                "split": "train",
                "performance_controls": {
                    name: 0.5 for name in CONTROL_NAMES
                },
            }
            path.write_text(
                json.dumps(record) + "\n" + json.dumps(record) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate source_id"):
                _load_records(path)

    def test_teacher_forced_targets_are_read_at_real_probe_divergence(self) -> None:
        records = {}
        probes = {"controls": {}}

        for index, name in enumerate(CONTROL_NAMES):
            low_id = f"{name}-low"
            high_id = f"{name}-high"
            records[low_id] = {
                "source_id": low_id,
                "split": "train",
                "tokens": [1, 16, 68, 170 + index * 2, 260, 192, 2],
                "performance_controls": {
                    control: (0.1 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            records[high_id] = {
                "source_id": high_id,
                "split": "train",
                "tokens": [1, 16, 68, 171 + index * 2, 260, 192, 2],
                "performance_controls": {
                    control: (0.9 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            probes["controls"][name] = {
                "prefix_tokens": [1, 16, 68],
                "prefix_length": 3,
                "first_target_divergence_index": 3,
                "low_profile": records[low_id]["performance_controls"],
                "high_profile": records[high_id]["performance_controls"],
                "low_record_source_id": low_id,
                "high_record_source_id": high_id,
            }

        report = _evaluate_with_model(
            FakeTeacherForcedModel(),
            records,
            probes,
            require_target_top1=True,
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(
            report["controls_with_both_targets_top1"],
            len(CONTROL_NAMES),
        )
        self.assertEqual(report["failures"], [])
        for name in CONTROL_NAMES:
            entry = report["controls"][name]
            self.assertEqual(entry["prefix_length"], 3)
            self.assertTrue(entry["low_target"]["target_top1"])
            self.assertTrue(entry["high_target"]["target_top1"])
            self.assertTrue(entry["low_target"]["target_legal_top1"])
            self.assertTrue(entry["high_target"]["target_legal_top1"])
            self.assertGreater(
                entry["control_effect"]["low_target_probability_lift_native_minus_counterfactual"],
                0.0,
            )
            self.assertGreater(
                entry["control_effect"]["high_target_probability_lift_native_minus_counterfactual"],
                0.0,
            )
            self.assertNotEqual(
                entry["low_target"]["target_token"],
                entry["high_target"]["target_token"],
            )
            self.assertEqual(
                entry["control_effect"]["target_logit_difference"],
                0.0,
            )


if __name__ == "__main__":
    unittest.main()
