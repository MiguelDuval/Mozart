#!/usr/bin/env python3
"""TDD contract for autoregressive conditioning responsiveness."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
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
    def test_mozart_token_grammar_accepts_valid_note_stream(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            validate_mozart_token_sequence,
        )

        report = validate_mozart_token_sequence(
            [1, 16, 68, 160, 258, 2]
        )
        self.assertTrue(report["valid"])
        self.assertIsNone(report["error"])

    def test_mozart_token_grammar_rejects_controller_token_as_note_velocity(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            validate_mozart_token_sequence,
        )

        report = validate_mozart_token_sequence(
            [1, 16, 68, 452, 452, 2]
        )
        self.assertFalse(report["valid"])
        self.assertEqual(report["index"], 3)
        self.assertEqual(report["token"], 452)
        self.assertIn("velocity token", report["error"])

    def test_mozart_token_grammar_rejects_missing_eos(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            validate_mozart_token_sequence,
        )

        report = validate_mozart_token_sequence(
            [1, 16, 68, 160, 258]
        )
        self.assertFalse(report["valid"])
        self.assertIn("end with EOS", report["error"])

    def test_bounded_generation_prefix_does_not_require_eos(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            validate_mozart_token_sequence,
        )

        complete = validate_mozart_token_sequence(
            [1, 16, 68, 160, 258],
            require_eos=False,
        )
        self.assertTrue(complete["valid"])
        self.assertFalse(complete["complete"])

        open_note = validate_mozart_token_sequence(
            [1, 16, 68],
            require_eos=False,
        )
        self.assertTrue(open_note["valid"])
        self.assertFalse(open_note["complete"])

        open_note_after_velocity = validate_mozart_token_sequence(
            [1, 16, 68, 160],
            require_eos=False,
        )
        self.assertTrue(open_note_after_velocity["valid"])
        self.assertFalse(open_note_after_velocity["complete"])

        malformed = validate_mozart_token_sequence(
            [1, 16, 68, 452],
            require_eos=False,
        )
        self.assertFalse(malformed["valid"])
        self.assertEqual(malformed["token"], 452)

    def test_probe_loader_rejects_malformed_grammar_prefix(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            load_sequence_probe_file,
        )

        payload = {
            "schema_version": 1,
            "fixture_revision": "mozart-conditioning-fixture-v1",
            "status": "synthetic-conditioning-sequence-probes",
            "controls": {
                name: {
                    "prefix_tokens": (
                        [1, 16, 68, 452]
                        if name == "density"
                        else [1, 16, 68]
                    ),
                    "prefix_length": (
                        4 if name == "density" else 3
                    ),
                    "first_target_divergence_index": (
                        4 if name == "density" else 3
                    ),
                }
                for name in (
                    "density",
                    "energy",
                    "syncopation",
                    "swing",
                    "variation",
                )
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sequence-probes.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "valid MIDI grammar prefix",
            ):
                load_sequence_probe_file(path)

    def test_loads_fixture_derived_control_probe_prefixes(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            load_sequence_probe_file,
        )

        payload = {
            "schema_version": 1,
            "fixture_revision": "mozart-conditioning-fixture-v1",
            "status": "synthetic-conditioning-sequence-probes",
            "controls": {
                name: {
                    "prefix_tokens": [1, 16 + index],
                    "prefix_length": 2,
                    "first_target_divergence_index": 2,
                }
                for index, name in enumerate(
                    (
                        "density",
                        "energy",
                        "syncopation",
                        "swing",
                        "variation",
                    )
                )
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sequence-probes.json"
            path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            probes = load_sequence_probe_file(path)

        self.assertEqual(
            probes["density"],
            (1, 16),
        )
        self.assertEqual(
            probes["variation"],
            (1, 20),
        )

    def test_grammar_next_token_mask_matches_frozen_event_order(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            is_allowed_next_token,
        )

        self.assertTrue(is_allowed_next_token([1], 16))
        self.assertTrue(is_allowed_next_token([1], 193))
        self.assertFalse(is_allowed_next_token([1], 68))

        self.assertTrue(is_allowed_next_token([1, 16], 68))
        self.assertTrue(is_allowed_next_token([1, 16], 352))
        self.assertFalse(is_allowed_next_token([1, 16], 193))

        self.assertTrue(is_allowed_next_token([1, 16, 68], 160))
        self.assertTrue(is_allowed_next_token([1, 16, 68], 161))
        self.assertFalse(is_allowed_next_token([1, 16, 68], 352))

        self.assertTrue(
            is_allowed_next_token([1, 16, 68, 160], 256)
        )
        self.assertFalse(
            is_allowed_next_token([1, 16, 68, 160], 160)
        )

        self.assertTrue(
            is_allowed_next_token([1, 16, 68, 160, 256], 2)
        )
        self.assertTrue(
            is_allowed_next_token([1, 16, 68, 160, 256], 68)
        )
        self.assertTrue(
            is_allowed_next_token([1, 16, 68, 160, 256, 193], 68)
        )
        self.assertFalse(
            is_allowed_next_token([1, 16, 68, 160, 256, 193], 160)
        )

        self.assertTrue(
            is_allowed_next_token([1, 16, 352], 480)
        )
        self.assertFalse(
            is_allowed_next_token([1, 16, 352], 256)
        )

    def test_grammar_constrained_generation_uses_only_allowed_logits(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            _grammar_allowed_mask,
            _greedy_token,
        )
        import numpy as np

        tokens = [1, 16, 68]
        logits = np.full(512, -1000.0, dtype=np.float32)
        logits[68] = 1000.0
        logits[500] = 500.0
        logits[160] = 1.0

        mask = _grammar_allowed_mask(tokens)
        self.assertFalse(mask[68])
        self.assertTrue(mask[160])
        self.assertTrue(mask[191])
        self.assertEqual(
            _greedy_token(logits, allowed_mask=mask),
            160,
        )

    def test_control_specific_prefix_is_used(self) -> None:
        from evaluate_mozart_conditioning_sequence import (
            evaluate_sequence_responsiveness,
        )

        prefixes = {
            "density": (1,),
            "energy": (1, 16),
            "syncopation": (1, 16, 68),
            "swing": (1, 16, 68, 177),
            "variation": (1, 16),
        }
        report = evaluate_sequence_responsiveness(
            FakeGreedyModel(responsive=True),
            max_generated_tokens=6,
            prefix_tokens=(1, 16, 92),
            prefix_tokens_by_control=prefixes,
            require_divergence=True,
        )

        for name, prefix in prefixes.items():
            self.assertEqual(
                report["controls"][name]["prefix_tokens"],
                list(prefix),
            )
            self.assertEqual(
                report["controls"][name]["prefix_length"],
                len(prefix),
            )


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
