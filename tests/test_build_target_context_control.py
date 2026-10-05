#!/usr/bin/env python3
"""Tests for the target-only target-diversity / canonical-conditioning control arm."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_conditioning_context_control import BASE_CONTEXT, CONDITIONING_FIELDS
from build_target_context_control import build_target_context_control


class TargetOnlyControlTests(unittest.TestCase):
    def _record(self, index: int) -> dict:
        conditioning = dict(BASE_CONTEXT)
        conditioning.update(
            {
                "style": "techno" if index % 2 else "electronic",
                "substyle": "techno",
                "mood": "driving",
                "rhythm": "straight",
                "role": "bass",
                "seed": 1000 + index,
            }
        )
        return {
            "source_id": f"diverse-{index}",
            "source_path": f"midi/control-probe-{index:02d}-v{index % 2}.mid",
            "tokens": [10, 100 + index, 20, 30],
            "target_sha256": f"{index + 1:064x}"[-64:],
            "performance_controls": {
                "density": 0.5,
                "energy": 0.5,
                "syncopation": 0.5,
                "swing": 0.5,
                "variation": 0.5,
            },
            "conditioning": conditioning,
        }

    def test_build_preserves_targets_and_canonicalizes_conditioning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diverse.jsonl"
            source_records = [self._record(i) for i in range(20)]
            source.write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in source_records),
                encoding="utf-8",
            )

            output = root / "out"
            contract = build_target_context_control(source, output)
            output_records = [
                json.loads(line)
                for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(contract["status"], "PASS")
        self.assertEqual(contract["input_train_records"], 20)
        self.assertEqual(contract["output_train_records"], 20)
        self.assertTrue(contract["target_tokens_fixed_against_input"])
        self.assertTrue(contract["target_hashes_fixed_against_input"])
        self.assertTrue(contract["source_paths_fixed_against_input"])
        self.assertTrue(contract["performance_controls_fixed_against_input"])
        self.assertTrue(contract["conditioning_seed_fixed_against_input"])
        self.assertEqual(len(output_records), 20)

        for original, output_record in zip(source_records, output_records):
            self.assertEqual(original["source_id"], output_record["source_id"])
            self.assertEqual(original["tokens"], output_record["tokens"])
            self.assertEqual(original["target_sha256"], output_record["target_sha256"])
            self.assertEqual(original["source_path"], output_record["source_path"])
            self.assertEqual(
                original["performance_controls"],
                output_record["performance_controls"],
            )
            self.assertEqual(
                original["conditioning"]["seed"],
                output_record["conditioning"]["seed"],
            )
            self.assertEqual(
                {field: output_record["conditioning"][field] for field in CONDITIONING_FIELDS},
                BASE_CONTEXT,
            )

    def test_rejects_canonical_conditioning_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diverse.jsonl"
            source_records = [self._record(i) for i in range(20)]
            for i, record in enumerate(source_records):
                record["source_id"] = f"diverse-{i}"
                record["source_path"] = f"midi/control-probe-{i:02d}.mid"
                for field in CONDITIONING_FIELDS:
                    record["conditioning"][field] = BASE_CONTEXT[field]
            source.write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in source_records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires an input with diverse"):
                build_target_context_control(source, root / "out")

    def test_rejects_non_diverse_target_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diverse.jsonl"
            source_records = [self._record(0) for _ in range(20)]
            for i, record in enumerate(source_records):
                record["source_id"] = f"diverse-{i}"
                record["source_path"] = f"midi/control-probe-{i:02d}.mid"
                record["conditioning"]["style"] = "techno" if i % 2 else "electronic"
            source.write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in source_records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "at least 11 distinct target"):
                build_target_context_control(source, root / "out")


if __name__ == "__main__":
    unittest.main()
