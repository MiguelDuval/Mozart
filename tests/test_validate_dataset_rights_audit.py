#!/usr/bin/env python3
"""Tests for the Mozart dataset rights-audit validator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import validate_dataset_rights_audit


def pending_audit() -> dict:
    return {
        "schema_version": 1,
        "audit_id": "waivops-nrg-cp-zenodo-15304989-v1",
        "source_id": "waivops-nrg-cp",
        "name": "WaivOps NRG-CP",
        "status": "pending",
        "source": {
            "locator": "https://zenodo.org/records/15304989",
            "revision": "zenodo:15304989@1.0",
        },
        "archive": {
            "filename": "nrgcp_midi_dataset.tar.gz",
            "md5": "7443fe30674ef149aa4c23580044f597",
            "sha256": "PENDING",
        },
        "license": {
            "spdx_id": "CC-BY-4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/",
            "publisher": "Patchbanks / WaivOps",
        },
        "evidence": [
            {
                "id": "zenodo-record",
                "kind": "archive_record",
                "locator": "https://zenodo.org/records/15304989",
                "checked_on": "2026-10-05",
                "statement": "Zenodo record identifies version 1.0 and the published archive.",
            },
            {
                "id": "publisher-license-statement",
                "kind": "rights_statement",
                "locator": "https://github.com/patchbanks/WaivOps-NRG-CP",
                "checked_on": "2026-10-05",
                "statement": "Publisher states that recordings were sourced from verified composers and providers for copyright clearance.",
            },
            {
                "id": "cc-by-terms",
                "kind": "license_terms",
                "locator": "https://creativecommons.org/licenses/by/4.0/",
                "checked_on": "2026-10-05",
                "statement": "CC BY 4.0 permits commercial sharing/adaptation subject to its terms.",
            },
        ],
        "checks": {
            "immutable_source_revision": "verified",
            "license_scope": "verified",
            "rights_holder_authority": "pending",
            "commercial_training_permission": "pending",
            "redistribution_permission": "pending",
            "attribution_requirements": "verified",
            "archive_sha256": "pending",
            "file_inventory_sha256": "pending",
        },
        "file_inventory_sha256": "PENDING",
        "blockers": [
            "Obtain SHA-256 for the downloaded archive.",
            "Establish that the licensor had authority to grant commercial training and redistribution rights for all contained MIDI material.",
            "Build and verify the complete file inventory with per-file SHA-256 checksums and exact manifest match.",
        ],
    }


class RightsAuditTests(unittest.TestCase):
    def _validate_expect_failure(self, audit: dict) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(audit), encoding="utf-8")
            with self.assertRaises(SystemExit):
                validate_dataset_rights_audit.validate(path)

    def test_pending_candidate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(pending_audit()), encoding="utf-8")
            validate_dataset_rights_audit.validate(path)

    def test_checked_in_nrg_cp_audit_passes(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "dataset-rights-audit-waivops-nrg-cp-v1.json"
        )
        validate_dataset_rights_audit.validate(path)

    def test_approved_requires_all_checks(self) -> None:
        audit = pending_audit()
        audit["status"] = "approved"
        audit["blockers"] = []
        self._validate_expect_failure(audit)

    def test_approved_requires_concrete_hashes(self) -> None:
        audit = pending_audit()
        audit["status"] = "approved"
        audit["blockers"] = []
        for key in validate_dataset_rights_audit.REQUIRED_CHECKS:
            audit["checks"][key] = "verified"
        self._validate_expect_failure(audit)

    def test_fully_verified_approved_audit_passes(self) -> None:
        audit = pending_audit()
        audit["status"] = "approved"
        audit["blockers"] = []
        audit["authority_chain_audit"] = "authority-chain.json"
        digest = "a" * 64
        audit["archive"]["sha256"] = digest
        audit["file_inventory_sha256"] = digest
        for key in validate_dataset_rights_audit.REQUIRED_CHECKS:
            audit["checks"][key] = "verified"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "audit.json"
            path.write_text(json.dumps(audit), encoding="utf-8")
            (root / "authority-chain.json").write_text(
                json.dumps({"status": "approved"}), encoding="utf-8"
            )
            validate_dataset_rights_audit.validate(path)

    def test_approved_requires_authority_chain_audit(self) -> None:
        audit = pending_audit()
        audit["status"] = "approved"
        audit["blockers"] = []
        digest = "a" * 64
        audit["archive"]["sha256"] = digest
        audit["file_inventory_sha256"] = digest
        for key in validate_dataset_rights_audit.REQUIRED_CHECKS:
            audit["checks"][key] = "verified"
        self._validate_expect_failure(audit)

    def test_pending_sha_is_not_accepted_as_verified_check(self) -> None:
        audit = pending_audit()
        audit["checks"]["archive_sha256"] = "verified"
        audit["archive"]["sha256"] = "PENDING"
        audit["checks"]["file_inventory_sha256"] = "verified"
        audit["file_inventory_sha256"] = "PENDING"
        audit["status"] = "approved"
        audit["blockers"] = []
        self._validate_expect_failure(audit)


if __name__ == "__main__":
    unittest.main()
