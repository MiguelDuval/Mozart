#!/usr/bin/env python3
"""Tests for the Mozart dataset authority-chain validator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import validate_dataset_authority_chain


def pending_audit() -> dict:
    return {
        "schema_version": 1,
        "audit_id": "waivops-nrg-cp-zenodo-15304989-v1-authority-chain",
        "source_id": "waivops-nrg-cp",
        "source_revision": "zenodo:15304989@1.0",
        "status": "pending",
        "publisher": {
            "entities": ["WaivOps", "Patchbanks"],
            "role": "dataset project / manager",
        },
        "rights_questions": {
            "publisher_authority_to_license": "pending",
            "commercial_training_permission": "asserted",
            "redistribution_permission": "asserted",
            "attribution_requirement": "verified",
            "per_file_rights_coverage": "pending",
        },
        "evidence": [
            {
                "id": "publisher",
                "evidence_ref": "https://github.com/patchbanks/WaivOps-NRG-CP",
                "supports": ["publisher_provenance_statement"],
                "strength": "publisher_assertion",
            }
        ],
        "chain": {
            "source_material_rights_holder": {
                "status": "unidentified",
                "evidence_refs": [],
            },
            "rights_grant_to_waivops_or_patchbanks": {
                "status": "unproven",
                "evidence_refs": [],
            },
            "dataset_file_mapping_to_rights_grant": {
                "status": "unproven",
                "evidence_refs": [],
            },
            "grant_to_end_user_under_cc_by_4_0": {
                "status": "published",
                "evidence_refs": ["publisher"],
            },
        },
        "known_gaps": ["source-rights document not public"],
        "required_for_approval": ["obtain documentary authority evidence"],
    }


class AuthorityChainTests(unittest.TestCase):
    def validate(self, audit: dict, expect_failure: bool = False) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(audit), encoding="utf-8")
            if expect_failure:
                with self.assertRaises(SystemExit):
                    validate_dataset_authority_chain.validate(path)
            else:
                validate_dataset_authority_chain.validate(path)

    def test_pending_candidate_passes(self) -> None:
        self.validate(pending_audit())

    def test_unknown_evidence_reference_fails(self) -> None:
        audit = pending_audit()
        audit["chain"]["grant_to_end_user_under_cc_by_4_0"]["evidence_refs"] = ["missing"]
        self.validate(audit, expect_failure=True)

    def test_approved_requires_independent_authority_document(self) -> None:
        audit = pending_audit()
        audit["status"] = "approved"
        audit["known_gaps"] = []
        for key in audit["rights_questions"]:
            audit["rights_questions"][key] = "verified"
        audit["chain"]["rights_grant_to_waivops_or_patchbanks"]["evidence_refs"] = ["publisher"]
        audit["chain"]["dataset_file_mapping_to_rights_grant"]["evidence_refs"] = ["publisher"]
        self.validate(audit, expect_failure=True)

    def test_approved_with_document_and_file_mapping_passes(self) -> None:
        audit = pending_audit()
        audit["status"] = "approved"
        audit["known_gaps"] = []
        for key in audit["rights_questions"]:
            audit["rights_questions"][key] = "verified"
        audit["evidence"].extend([
            {
                "id": "authority-doc",
                "evidence_ref": "https://example.invalid/authority.pdf",
                "supports": ["rights_grant"],
                "strength": "independent_document",
            },
            {
                "id": "file-manifest",
                "evidence_ref": "https://example.invalid/manifest.json",
                "supports": ["per_file_rights_coverage"],
                "strength": "file_mapping",
            },
        ])
        audit["chain"]["source_material_rights_holder"]["status"] = "documented"
        audit["chain"]["source_material_rights_holder"]["evidence_refs"] = ["authority-doc"]
        audit["chain"]["rights_grant_to_waivops_or_patchbanks"]["status"] = "documented"
        audit["chain"]["rights_grant_to_waivops_or_patchbanks"]["evidence_refs"] = ["authority-doc"]
        audit["chain"]["dataset_file_mapping_to_rights_grant"]["status"] = "documented"
        audit["chain"]["dataset_file_mapping_to_rights_grant"]["evidence_refs"] = ["file-manifest"]
        audit["chain"]["grant_to_end_user_under_cc_by_4_0"]["status"] = "documented"
        audit["chain"]["grant_to_end_user_under_cc_by_4_0"]["evidence_refs"] = ["authority-doc"]
        self.validate(audit)


if __name__ == "__main__":
    unittest.main()
