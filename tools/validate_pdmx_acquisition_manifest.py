#!/usr/bin/env python3
"""Validate the pinned PDMX acquisition manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MD5_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^(?:[0-9a-f]{64}|PENDING)$")
REQUIRED_NAMES = {"mid.tar.gz", "PDMX.csv", "subset_paths.tar.gz"}
REQUIRED_ROLES = {"MIDI corpus", "authoritative metadata and subset manifest", "published subset path lists"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read manifest {path}: {exc}")

    if not isinstance(data, dict):
        fail("manifest root must be an object")
    if data.get("schema_version") != 1:
        fail("schema_version must be 1")
    if not isinstance(data.get("manifest_id"), str) or not data["manifest_id"].strip():
        fail("manifest_id must be a non-empty string")

    source = data.get("source")
    if not isinstance(source, dict):
        fail("source must be an object")
    if source.get("revision") != "v9":
        fail("source.revision must be v9")
    for key in ("name", "doi", "record", "upstream_code_repository", "upstream_code_license"):
        if not isinstance(source.get(key), str) or not source[key].strip():
            fail(f"source.{key} must be a non-empty string")
    if source["upstream_code_license"] != "MIT":
        fail("source.upstream_code_license must document upstream PDMX code license as MIT")

    artifacts = data.get("published_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        fail("published_artifacts must contain exactly three artifacts")
    seen_names = set()
    seen_roles = set()
    for index, artifact in enumerate(artifacts):
        where = f"published_artifacts[{index}]"
        if not isinstance(artifact, dict):
            fail(f"{where} must be an object")
        name = artifact.get("name")
        role = artifact.get("role")
        if not isinstance(name, str) or not name.strip():
            fail(f"{where}.name must be a non-empty string")
        if name in seen_names:
            fail(f"duplicate artifact name: {name}")
        seen_names.add(name)
        if role not in REQUIRED_ROLES:
            fail(f"{where}.role is unsupported: {role}")
        seen_roles.add(role)
        md5 = artifact.get("md5")
        if not isinstance(md5, str) or not MD5_RE.fullmatch(md5):
            fail(f"{where}.md5 must be a lowercase 32-character hex MD5")
        local_sha256 = artifact.get("local_sha256")
        if not isinstance(local_sha256, str) or not SHA256_RE.fullmatch(local_sha256):
            fail(f"{where}.local_sha256 must be a lowercase SHA-256 or PENDING")

    if seen_names != REQUIRED_NAMES:
        fail("published_artifacts names do not match required v9 artifact set")
    if seen_roles != REQUIRED_ROLES:
        fail("published_artifacts roles are incomplete")

    scope = data.get("published_scope")
    if not isinstance(scope, dict):
        fail("published_scope must be an object")
    if scope.get("recommended_subset") != "no_license_conflict":
        fail("published_scope.recommended_subset must be no_license_conflict")
    for key in ("recommended_subset_rows", "reported_license_conflict_rows", "known_corrupt_original_files"):
        if not isinstance(scope.get(key), int) or scope[key] < 0:
            fail(f"published_scope.{key} must be a non-negative integer")
    percentage = scope.get("reported_license_conflict_percentage")
    if not isinstance(percentage, (int, float)) or percentage < 0:
        fail("published_scope.reported_license_conflict_percentage must be non-negative")

    legal = data.get("legal_status")
    if not isinstance(legal, dict):
        fail("legal_status must be an object")
    if legal.get("commercial_training_rights") != "requires_separate_rights_review":
        fail("commercial_training_rights must remain requires_separate_rights_review")
    if legal.get("redistribution_rights") != "requires_separate_rights_review":
        fail("redistribution_rights must remain requires_separate_rights_review")
    if legal.get("code_license_must_not_be_interpreted_as_dataset_content_license") is not True:
        fail("manifest must explicitly separate code license from dataset content rights")

    print(f"PASS: {path} is a valid pinned PDMX v9 acquisition manifest")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        validate(args.manifest)
    except SystemExit:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
