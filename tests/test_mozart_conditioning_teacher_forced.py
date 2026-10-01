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
            -1000.0,
            dtype=torch.float32,
        )
        for row in range(batch):
            values = performance_controls[row].tolist()
            index = next(
                index
                for index, value in enumerate(values)
                if value in (0.1, 0.9)
            )
            high = values[index] > 0.5
            token = 100 + index * 2 + int(high)
            logits[row, -1, token] = 100.0
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

    def test_counterfactual_window_isolates_control_effect(self) -> None:
        records = {}
        probes = {"controls": {}}

        for index, name in enumerate(CONTROL_NAMES):
            low_id = f"{name}-low"
            high_id = f"{name}-high"
            tokens = [1, 16, 68, 100 + index * 2, 160, 258, 2]
            records[low_id] = {
                "source_id": low_id,
                "split": "train",
                "tokens": tokens,
                "performance_controls": {
                    control: (0.1 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            records[high_id] = {
                "source_id": high_id,
                "split": "train",
                "tokens": tokens,
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
        for name in CONTROL_NAMES:
            entry = report["controls"][name]
            self.assertEqual(entry["window_step_count"], 4)
            self.assertEqual(
                entry["top1_changed_by_control_steps"],
                4,
            )
            deltas = [
                step["target_logit_delta_native_minus_counterfactual"]
                for step in entry["steps"]
            ]
            self.assertTrue(all(delta != 0.0 for delta in deltas))

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
                "tokens": [1, 16, 68, 100 + index * 2, 160, 258, 2],
                "performance_controls": {
                    control: (0.1 if control == name else 0.5)
                    for control in CONTROL_NAMES
                },
            }
            records[high_id] = {
                "source_id": high_id,
                "split": "train",
                "tokens": [1, 16, 68, 101 + index * 2, 160, 258, 2],
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
