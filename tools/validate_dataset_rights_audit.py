#!/usr/bin/env python3
"""Validate a non-production Mozart dataset rights-audit ledger."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
MD5_RE = re.compile(r"^[0-9a-fA-F]{32}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
STATUSES = {"pending", "approved"}
CHECK_VALUES = {"verified", "pending", "failed"}
REQUIRED_CHECKS = (
    "immutable_source_revision",
    "license_scope",
    "rights_holder_authority",
    "commercial_training_permission",
    "redistribution_permission",
    "attribution_requirements",
    "archive_sha256",
    "file_inventory_sha256",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_string(obj: dict, key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{where}.{key} must be a non-empty string")
    return value


def _require_http_url(value: str, where: str) -> None:
    if not (value.startswith("https://") or value.startswith("http://")):
        fail(f"{where} must be an HTTP(S) URL")


def _require_sha256(value: str, where: str, *, allow_pending: bool = False) -> None:
    if allow_pending and value == "PENDING":
        return
    if not SHA256_RE.fullmatch(value):
        expected = "a 64-character hex SHA-256"
        if allow_pending:
            expected += " or PENDING"
        fail(f"{where} must be {expected}")


def validate(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read rights audit {path}: {exc}")

    if not isinstance(data, dict):
        fail("audit root must be an object")
    if data.get("schema_version") != 1:
        fail("schema_version must be 1")

    require_string(data, "audit_id", "audit")
    source_id = require_string(data, "source_id", "audit")
    require_string(data, "name", "audit")
    status = data.get("status")
    if status not in STATUSES:
        fail("status must be pending or approved")

    source = data.get("source")
    if not isinstance(source, dict):
        fail("source must be an object")
    source_revision = require_string(source, "revision", "source")
    if source_revision == "PENDING":
        fail("source.revision must identify an immutable source revision")
    locator = require_string(source, "locator", "source")
    _require_http_url(locator, "source.locator")

    archive = data.get("archive")
    if not isinstance(archive, dict):
        fail("archive must be an object")
    require_string(archive, "filename", "archive")
    md5 = require_string(archive, "md5", "archive")
    if not MD5_RE.fullmatch(md5):
        fail("archive.md5 must be a 32-character hex checksum")
    archive_sha = require_string(archive, "sha256", "archive")
    _require_sha256(archive_sha, "archive.sha256", allow_pending=True)

    license_info = data.get("license")
    if not isinstance(license_info, dict):
        fail("license must be an object")
    require_string(license_info, "spdx_id", "license")
    license_url = require_string(license_info, "url", "license")
    _require_http_url(license_url, "license.url")
    require_string(license_info, "publisher", "license")

    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        fail("evidence must contain at least one item")
    evidence_ids: set[str] = set()
    for index, item in enumerate(evidence):
        where = f"evidence[{index}]"
        if not isinstance(item, dict):
            fail(f"{where} must be an object")
        evidence_id = require_string(item, "id", where)
        if evidence_id in evidence_ids:
            fail(f"duplicate evidence id: {evidence_id}")
        evidence_ids.add(evidence_id)
        kind = require_string(item, "kind", where)
        require_string(item, "statement", where)
        locator = require_string(item, "locator", where)
        _require_http_url(locator, f"{where}.locator")
        checked_on = require_string(item, "checked_on", where)
        if not DATE_RE.fullmatch(checked_on):
            fail(f"{where}.checked_on must be an ISO date")
        if kind not in {"dataset_page", "license_terms", "rights_statement", "archive_record"}:
            fail(f"{where}.kind is unsupported")

    checks = data.get("checks")
    if not isinstance(checks, dict):
        fail("checks must be an object")
    if set(checks) != set(REQUIRED_CHECKS):
        missing = sorted(set(REQUIRED_CHECKS) - set(checks))
        extra = sorted(set(checks) - set(REQUIRED_CHECKS))
        if missing:
            fail("checks missing: " + ", ".join(missing))
        if extra:
            fail("checks contain unsupported keys: " + ", ".join(extra))
    for key in REQUIRED_CHECKS:
        if checks[key] not in CHECK_VALUES:
            fail(f"checks.{key} must be verified, pending, or failed")

    blockers = data.get("blockers")
    if not isinstance(blockers, list) or any(
        not isinstance(item, str) or not item.strip() for item in blockers
    ):
        fail("blockers must be a list of non-empty strings")

    authority_chain_audit = data.get("authority_chain_audit")
    if authority_chain_audit is not None:
        if not isinstance(authority_chain_audit, str) or not authority_chain_audit.strip():
            fail("authority_chain_audit must be a non-empty relative path when present")
        authority_path = Path(authority_chain_audit)
        if authority_path.is_absolute() or ".." in authority_path.parts:
            fail("authority_chain_audit must be a safe relative path")

    file_inventory_sha = data.get("file_inventory_sha256")
    if not isinstance(file_inventory_sha, str):
        fail("file_inventory_sha256 must be a string")
    _require_sha256(file_inventory_sha, "file_inventory_sha256", allow_pending=True)

    if status == "approved":
        if blockers:
            fail("approved audits must have no blockers")
        unresolved = [key for key in REQUIRED_CHECKS if checks[key] != "verified"]
        if unresolved:
            fail(
                "approved audits require all checks to be verified: "
                + ", ".join(unresolved)
            )
        _require_sha256(archive_sha, "archive.sha256")
        _require_sha256(file_inventory_sha, "file_inventory_sha256")
        if not authority_chain_audit:
            fail("approved audits require authority_chain_audit")
        authority_file = (path.parent / authority_chain_audit).resolve()
        if not authority_file.is_file():
            fail(f"authority-chain audit file does not exist: {authority_chain_audit}")
        try:
            authority_data = json.loads(authority_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"cannot read authority-chain audit {authority_file}: {exc}")
        if not isinstance(authority_data, dict) or authority_data.get("status") != "approved":
            fail("approved rights audits require an approved authority-chain audit")

    print(
        f"PASS: {path} is a valid Mozart rights audit "
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
