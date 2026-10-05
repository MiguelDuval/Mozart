#!/usr/bin/env python3
"""Tests for the joint target + conditioning diversity factorial arm."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_conditioning_context_control import (
    BASE_CONTEXT,
    CONDITIONING_CONTEXT_PROFILES,
    CONDITIONING_FIELDS,
)
from build_joint_context_diversity import build_joint_context_diverse


class JointContextDiversityTests(unittest.TestCase):
    def _record(self, index: int, variant: int) -> dict:
        conditioning = dict(BASE_CONTEXT)
        source_id = (
            f"base-{index}" if variant == 0 else f"base-{index}-context-v1"
        )
        source_path = f"midi/control-probe-{index:02d}-v{variant}.mid"
        return {
            "source_id": source_id,
            "source_path": source_path,
            "tokens": [10, 100 + index, 20 + variant, 30],
            "target_sha256": f"{index * 2 + variant + 1:064x}",
            "performance_controls": {
                "density": 0.5,
                "energy": 0.5,
                "syncopation": 0.5,
                "swing": 0.5,
                "variation": 0.5,
            },
            "conditioning": {**conditioning, "seed": 5000 + index + variant * 1000},
        }

    def test_build_changes_only_variant_conditioning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diverse.jsonl"
            records = [
                self._record(index, variant)
                for variant in (0, 1)
                for index in range(10)
            ]
            source.write_text(
                "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
                encoding="utf-8",
            )

            output = root / "out"
            contract = build_joint_context_diverse(source, output)

            output_records = [
                json.loads(line)
                for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(contract["status"], "PASS")
        self.assertEqual(contract["output_train_records"], 20)
        self.assertEqual(contract["conditioned_variant_positions"], 10)
        self.assertTrue(contract["target_signature_fixed"])
        self.assertEqual(contract["distinct_conditioning_contexts"], 11)

        by_id = {record["source_id"]: record for record in output_records}
        for index in range(10):
            base = by_id[f"base-{index}"]
            variant = by_id[f"base-{index}-context-v1"]
            self.assertEqual(
                {field: base["conditioning"][field] for field in CONDITIONING_FIELDS},
                BASE_CONTEXT,
            )
            self.assertEqual(
                {field: variant["conditioning"][field] for field in CONDITIONING_FIELDS},
                CONDITIONING_CONTEXT_PROFILES[index],
            )
            self.assertEqual(base["conditioning"]["seed"], 5000 + index)
            self.assertEqual(variant["conditioning"]["seed"], 5000 + index + 1000)

        for original, output_record in zip(records, output_records):
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

    def test_rejects_missing_or_orphaned_variants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diverse.jsonl"
            records = [
                self._record(index, variant)
                for variant in (0, 1)
                for index in range(10)
            ]
            records[-1]["source_id"] = "unpaired-context-v1"
            source.write_text(
                "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "base/variant source pairing mismatch"):
                build_joint_context_diverse(source, root / "out")


if __name__ == "__main__":
    unittest.main()
