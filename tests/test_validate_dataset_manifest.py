#!/usr/bin/env python3
"""Tests for dataset manifest validation."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import validate_dataset_manifest


class DatasetManifestValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "docs"
                / "dataset-manifest.example.json"
            ).read_text(encoding="utf-8")
        )

    def _validate_expect_failure(self, manifest: dict) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                validate_dataset_manifest.validate(path)

    def test_template_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(self.template, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            validate_dataset_manifest.validate(path)

    def test_audited_manifest_requires_concrete_spdx_id(self) -> None:
        manifest = copy.deepcopy(self.template)
        manifest["status"] = "audited"
        manifest["sources"][0]["license"]["commercial_use"] = "allowed"
        manifest["sources"][0]["license"]["redistribution"] = "allowed"
        manifest["sources"][0]["license"]["attribution"] = "required"
        manifest["sources"][0]["revision"] = "rev-001"
        manifest["sources"][0]["provenance"]["rights_evidence"] = "rights-review-001"
        self._validate_expect_failure(manifest)

    def test_duplicate_source_ids_are_rejected(self) -> None:
        manifest = copy.deepcopy(self.template)
        manifest["sources"].append(copy.deepcopy(manifest["sources"][0]))
        self._validate_expect_failure(manifest)

    def test_duplicate_manifest_file_paths_are_rejected(self) -> None:
        manifest = copy.deepcopy(self.template)
        extra = copy.deepcopy(manifest["sources"][0])
        extra["source_id"] = "other-source"
        manifest["sources"].append(extra)
        self._validate_expect_failure(manifest)


if __name__ == "__main__":
    unittest.main()
