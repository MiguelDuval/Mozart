#!/usr/bin/env python3
"""Validate the machine-readable authority-chain audit for a Mozart dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATUS_VALUES = {"pending", "approved"}
RIGHTS_VALUES = {"pending", "asserted", "verified", "failed"}
STRENGTH_VALUES = {
    "public_record",
    "publisher_assertion",
    "independent_document",
    "file_mapping",
}
REQUIRED_RIGHTS = (
    "publisher_authority_to_license",
    "commercial_training_permission",
    "redistribution_permission",
    "attribution_requirement",
    "per_file_rights_coverage",
)
REQUIRED_CHAIN = (
    "source_material_rights_holder",
    "rights_grant_to_waivops_or_patchbanks",
    "dataset_file_mapping_to_rights_grant",
    "grant_to_end_user_under_cc_by_4_0",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def nonempty_string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{where} must be a non-empty string")
    return value


def nonempty_list(value: object, where: str) -> list:
    if not isinstance(value, list) or not value:
        fail(f"{where} must be a non-empty list")
    return value


def validate(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read authority-chain audit {path}: {exc}")

    if not isinstance(data, dict):
        fail("audit root must be an object")
    if data.get("schema_version") != 1:
        fail("schema_version must be 1")

    source_id = nonempty_string(data.get("source_id"), "audit.source_id")
    nonempty_string(data.get("audit_id"), "audit.audit_id")
    nonempty_string(data.get("source_revision"), "audit.source_revision")
    status = data.get("status")
    if status not in STATUS_VALUES:
        fail("status must be pending or approved")

    publisher = data.get("publisher")
    if not isinstance(publisher, dict):
        fail("publisher must be an object")
    entities = nonempty_list(publisher.get("entities"), "publisher.entities")
    if any(not isinstance(item, str) or not item.strip() for item in entities):
        fail("publisher.entities must contain only non-empty strings")
    nonempty_string(publisher.get("role"), "publisher.role")

    rights = data.get("rights_questions")
    if not isinstance(rights, dict):
        fail("rights_questions must be an object")
    if set(rights) != set(REQUIRED_RIGHTS):
        missing = sorted(set(REQUIRED_RIGHTS) - set(rights))
        extra = sorted(set(rights) - set(REQUIRED_RIGHTS))
        if missing:
            fail("rights_questions missing: " + ", ".join(missing))
        if extra:
            fail("rights_questions contain unsupported keys: " + ", ".join(extra))
    for key in REQUIRED_RIGHTS:
        if rights[key] not in RIGHTS_VALUES:
            fail(f"rights_questions.{key} must be pending, asserted, verified, or failed")

    evidence = nonempty_list(data.get("evidence"), "evidence")
    evidence_ids: set[str] = set()
    strength_by_id: dict[str, str] = {}
    for index, item in enumerate(evidence):
        where = f"evidence[{index}]"
        if not isinstance(item, dict):
            fail(f"{where} must be an object")
        evidence_id = nonempty_string(item.get("id"), f"{where}.id")
        if evidence_id in evidence_ids:
            fail(f"duplicate evidence id: {evidence_id}")
        evidence_ids.add(evidence_id)
        nonempty_string(item.get("evidence_ref"), f"{where}.evidence_ref")
        supports = item.get("supports")
        if not isinstance(supports, list) or any(
            not isinstance(s, str) or not s.strip() for s in supports
        ):
            fail(f"{where}.supports must be a list of non-empty strings")
        strength = item.get("strength")
        if strength not in STRENGTH_VALUES:
            fail(f"{where}.strength is unsupported: {strength}")
        strength_by_id[evidence_id] = strength

    chain = data.get("chain")
    if not isinstance(chain, dict):
        fail("chain must be an object")
    if set(chain) != set(REQUIRED_CHAIN):
        missing = sorted(set(REQUIRED_CHAIN) - set(chain))
        extra = sorted(set(chain) - set(REQUIRED_CHAIN))
        if missing:
            fail("chain missing: " + ", ".join(missing))
        if extra:
            fail("chain contains unsupported keys: " + ", ".join(extra))

    for key in REQUIRED_CHAIN:
        item = chain[key]
        if not isinstance(item, dict):
            fail(f"chain.{key} must be an object")
        nonempty_string(item.get("status"), f"chain.{key}.status")
        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or ref not in evidence_ids for ref in refs
        ):
            fail(
                f"chain.{key}.evidence_refs must contain only known evidence ids"
            )

    gaps = data.get("known_gaps")
    if not isinstance(gaps, list) or any(
        not isinstance(item, str) or not item.strip() for item in gaps
    ):
        fail("known_gaps must be a list of non-empty strings")

    required = nonempty_list(data.get("required_for_approval"), "required_for_approval")
    if any(not isinstance(item, str) or not item.strip() for item in required):
        fail("required_for_approval must contain only non-empty strings")

    if status == "approved":
        if gaps:
            fail("approved authority-chain audits must have no known_gaps")
        unresolved = [
            key
            for key in REQUIRED_RIGHTS
            if rights[key] != "verified"
        ]
        if unresolved:
            fail(
                "approved authority-chain audits require all rights questions verified: "
                + ", ".join(unresolved)
            )
        authority_refs = chain["rights_grant_to_waivops_or_patchbanks"]["evidence_refs"]
        mapping_refs = chain["dataset_file_mapping_to_rights_grant"]["evidence_refs"]
        if not any(strength_by_id[ref] == "independent_document" for ref in authority_refs):
            fail("approved authority-chain audit requires independent documentary evidence for the rights grant")
        if not any(strength_by_id[ref] == "file_mapping" for ref in mapping_refs):
            fail("approved authority-chain audit requires file-mapping evidence for corpus coverage")

    print(
        f"PASS: {path} is a valid Mozart authority-chain audit "
        f"(source_id={source_id}, status={status})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    args = parser.parse_args()
    try:
        validate(args.audit)
    except SystemExit:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
