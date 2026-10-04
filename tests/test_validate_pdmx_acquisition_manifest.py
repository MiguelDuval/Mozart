#!/usr/bin/env python3
"""Tests for the PDMX acquisition manifest validator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import validate_pdmx_acquisition_manifest


def valid_manifest() -> dict:
    return {
        "schema_version": 1,
        "manifest_id": "pdmx-zenodo-15571083-v9-acquisition",
        "status": "pending_local_acquisition",
        "source": {
            "name": "PDMX",
            "doi": "10.5281/zenodo.15571083",
            "record": "https://zenodo.org/records/15571083",
            "revision": "v9",
            "upstream_code_repository": "https://github.com/pnlong/PDMX",
            "upstream_code_license": "MIT",
        },
        "published_artifacts": [
            {"name": "mid.tar.gz", "role": "MIDI corpus", "md5": "a" * 32, "local_sha256": "PENDING"},
            {"name": "PDMX.csv", "role": "authoritative metadata and subset manifest", "md5": "b" * 32, "local_sha256": "PENDING"},
            {"name": "subset_paths.tar.gz", "role": "published subset path lists", "md5": "c" * 32, "local_sha256": "PENDING"},
        ],
        "published_scope": {
            "recommended_subset": "no_license_conflict",
            "recommended_subset_rows": 222856,
            "reported_license_conflict_rows": 31221,
            "reported_license_conflict_percentage": 12.29,
            "known_corrupt_original_files": 42,
        },
        "legal_status": {
            "technical_provenance": "pending_local_acquisition",
            "commercial_training_rights": "requires_separate_rights_review",
            "redistribution_rights": "requires_separate_rights_review",
            "code_license_must_not_be_interpreted_as_dataset_content_license": True,
        },
    }


class PdmxManifestTests(unittest.TestCase):
    def run_validation(self, manifest: dict, expect_failure: bool = False) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            if expect_failure:
                with self.assertRaises(SystemExit):
                    validate_pdmx_acquisition_manifest.validate(path)
            else:
                validate_pdmx_acquisition_manifest.validate(path)

    def test_valid_manifest_passes(self) -> None:
        self.run_validation(valid_manifest())

    def test_wrong_revision_fails(self) -> None:
        manifest = valid_manifest()
        manifest["source"]["revision"] = "v8"
        self.run_validation(manifest, expect_failure=True)

    def test_unknown_artifact_fails(self) -> None:
        manifest = valid_manifest()
        manifest["published_artifacts"][0]["name"] = "other.tar.gz"
        self.run_validation(manifest, expect_failure=True)

    def test_code_license_separation_is_required(self) -> None:
        manifest = valid_manifest()
        manifest["legal_status"]["code_license_must_not_be_interpreted_as_dataset_content_license"] = False
        self.run_validation(manifest, expect_failure=True)


if __name__ == "__main__":
    unittest.main()
