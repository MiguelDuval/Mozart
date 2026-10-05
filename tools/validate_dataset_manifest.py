#!/usr/bin/env python3
"""Validate a Mozart dataset manifest with only Python's standard library."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
SPDX_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_string(obj: dict, key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{where}.{key} must be a non-empty string")
    return value


def validate(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON manifest {path}: {exc}")

    if not isinstance(data, dict):
        fail("manifest root must be an object")
    if data.get("schema_version") != 1:
        fail("schema_version must be 1")
    require_string(data, "manifest_id", "manifest")
    status = data.get("status")
    if status not in {"template", "audited", "release"}:
        fail("status must be template, audited, or release")
    if data.get("license_policy") != "commercial-compatible-only":
        fail("license_policy must be commercial-compatible-only")
    if data.get("project_vocabulary_id") != "mozart-midi-events-v1":
        fail("project_vocabulary_id must be mozart-midi-events-v1")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        fail("sources must contain at least one source")

    seen_source_ids: set[str] = set()
    seen_file_paths: set[str] = set()

    for index, source in enumerate(sources):
        where = f"sources[{index}]"
        if not isinstance(source, dict):
            fail(f"{where} must be an object")
        for key in ("source_id", "name", "locator", "revision"):
            require_string(source, key, where)

        source_id = source["source_id"]
        if source_id in seen_source_ids:
            fail(f"duplicate source_id: {source_id}")
        seen_source_ids.add(source_id)

        license_info = source.get("license")
        if not isinstance(license_info, dict):
            fail(f"{where}.license must be an object")
        for key in ("spdx_id", "commercial_use", "redistribution", "attribution"):
            require_string(license_info, key, f"{where}.license")
        for key in ("commercial_use", "redistribution"):
            if license_info[key] not in {"allowed", "requires-review", "prohibited"}:
                fail(f"{where}.license.{key} has invalid classification")
        if license_info["attribution"] not in {"required", "not-required", "requires-review"}:
            fail(f"{where}.license.attribution has invalid classification")

        if status in {"audited", "release"}:
            spdx_id = license_info["spdx_id"]
            if spdx_id == "REPLACE" or not SPDX_ID_RE.fullmatch(spdx_id):
                fail(
                    f"{where}.license.spdx_id must be a concrete SPDX license identifier "
                    f"for {status} manifests"
                )

        files = source.get("files")
        if not isinstance(files, list) or not files:
            fail(f"{where}.files must contain at least one file")
        for file_index, item in enumerate(files):
            file_where = f"{where}.files[{file_index}]"
            if not isinstance(item, dict):
                fail(f"{file_where} must be an object")
            path_value = require_string(item, "path", file_where)
            if path_value in seen_file_paths:
                fail(f"duplicate manifest file path: {path_value}")
            seen_file_paths.add(path_value)
            checksum = require_string(item, "sha256", file_where)
            if checksum != "REPLACE" and not SHA256_RE.fullmatch(checksum):
                fail(f"{file_where}.sha256 must be a 64-character hex checksum or REPLACE")
            size = item.get("size_bytes")
            if not isinstance(size, int) or size < 0:
                fail(f"{file_where}.size_bytes must be a non-negative integer")

        provenance = source.get("provenance")
        if not isinstance(provenance, dict):
            fail(f"{where}.provenance must be an object")
        require_string(provenance, "provider", f"{where}.provenance")
        acquisition_date = require_string(provenance, "acquisition_date", f"{where}.provenance")
        if acquisition_date != "YYYY-MM-DD" and not DATE_RE.fullmatch(acquisition_date):
            fail(f"{where}.provenance.acquisition_date must be YYYY-MM-DD or an ISO date")
        require_string(provenance, "rights_evidence", f"{where}.provenance")

        if status in {"audited", "release"}:
            if license_info["commercial_use"] != "allowed":
                fail(f"{where}.license.commercial_use must be allowed for {status} manifests")
            if license_info["redistribution"] != "allowed":
                fail(f"{where}.license.redistribution must be allowed for {status} manifests")
            if provenance["rights_evidence"].startswith("REPLACE"):
                fail(f"{where}.provenance.rights_evidence must be recorded for {status} manifests")
            if source["revision"].startswith("REPLACE"):
                fail(f"{where}.revision must be immutable for {status} manifests")

    splits = data.get("splits")
    if not isinstance(splits, dict):
        fail("splits must be an object")
    for key in ("train", "validation", "test"):
        require_string(splits, key, "splits")

    normalization = data.get("normalization")
    if not isinstance(normalization, dict):
        fail("normalization must be an object")
    require_string(normalization, "revision", "normalization")
    max_events = normalization.get("max_events_per_example")
    if not isinstance(max_events, int) or not 1 <= max_events <= 4096:
        fail("normalization.max_events_per_example must be 1..4096")

    examples = data.get("examples")
    if not isinstance(examples, dict):
        fail("examples must be an object")
    min_bars = examples.get("min_bars")
    max_bars = examples.get("max_bars")
    if not isinstance(min_bars, int) or not isinstance(max_bars, int):
        fail("examples min_bars/max_bars must be integers")
    if not 1 <= min_bars <= max_bars <= 16:
        fail("examples min_bars/max_bars must satisfy 1 <= min <= max <= 16")

    print(f"PASS: {path} is a valid Mozart dataset manifest (status={status})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} MANIFEST.json", file=sys.stderr)
        raise SystemExit(2)
    validate(Path(sys.argv[1]))
