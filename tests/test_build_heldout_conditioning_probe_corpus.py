#!/usr/bin/env python3
"""Tests for evaluation-only held-out conditioning probes."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_conditioning_fixture_corpus import CONTROL_PROFILES
from build_heldout_conditioning_probe_corpus import build_heldout_probe_corpus


class HeldoutConditioningProbeTests(unittest.TestCase):
    def _validation_fixture(self, root: Path) -> Path:
        path = root / "validation.jsonl"
        records = []
        for index in range(4):
            records.append(
                {
                    "source_id": f"validation-{index}",
                    "source_revision": "mozart-conditioning-fixture-v2",
                    "split": "validation",
                    "conditioning": {
                        "style": "electronic",
                        "substyle": "techno",
                        "mood": "driving",
                        "rhythm": "straight",
                        "role": "bass",
                        "seed": 5000 + index,
                    },
                    "performance_controls": dict(CONTROL_PROFILES[10 + index]),
                }
            )
        path.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )
        return path

    def test_builds_four_contexts_and_twenty_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validation = self._validation_fixture(root)
            output = root / "probes"
            manifest = build_heldout_probe_corpus(validation, output)

            self.assertEqual(manifest["context_count"], 4)
            self.assertEqual(manifest["record_count"], 40)
            self.assertEqual(manifest["probe_count"], 20)

            for context in manifest["contexts"]:
                records = [
                    json.loads(line)
                    for line in (
                        output / context["records_path"]
                    ).read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                probes = json.loads(
                    (output / context["probe_path"]).read_text(encoding="utf-8")
                )
                self.assertEqual(len(records), 10)
                self.assertEqual(len(probes["controls"]), 5)
                self.assertTrue(
                    all(record["split"] == "validation" for record in records)
                )
                for entry in probes["controls"].values():
                    self.assertGreaterEqual(entry["prefix_length"], 1)
                    self.assertEqual(
                        entry["first_target_divergence_index"],
                        entry["prefix_length"],
                    )
                    low = next(
                        record
                        for record in records
                        if record["source_id"] == entry["low_record_source_id"]
                    )
                    high = next(
                        record
                        for record in records
                        if record["source_id"] == entry["high_record_source_id"]
                    )
                    prefix = entry["prefix_tokens"]
                    self.assertEqual(low["tokens"][:len(prefix)], prefix)
                    self.assertEqual(high["tokens"][:len(prefix)], prefix)
                    self.assertNotEqual(
                        low["tokens"][len(prefix)],
                        high["tokens"][len(prefix)],
                    )
                    self.assertEqual(low["conditioning"]["seed"], high["conditioning"]["seed"])
                    self.assertNotEqual(low["tokens"], high["tokens"])

    def test_rejects_non_validation_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validation = self._validation_fixture(root)
            records = [
                json.loads(line)
                for line in validation.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            records[0]["split"] = "train"
            validation.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "split=validation"):
                build_heldout_probe_corpus(validation, root / "probes")

    def test_requires_four_contexts_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            validation = self._validation_fixture(root)
            records = [
                json.loads(line)
                for line in validation.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ][:3]
            validation.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "expected at least 4"):
                build_heldout_probe_corpus(validation, root / "probes")
