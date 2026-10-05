#!/usr/bin/env python3
"""Verify that a discovered MIDI inventory exactly matches an audited manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc


def _load_inventory(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read inventory {path}: {exc}") from exc

    entries: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_number}: entry must be an object")

        path_value = item.get("path")
        checksum = item.get("sha256")
        size = item.get("size_bytes")
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError(f"{path}:{line_number}: path is required")
        if (
            not isinstance(checksum, str)
            or len(checksum) != 64
            or checksum == "REPLACE"
            or any(ch not in "0123456789abcdefABCDEF" for ch in checksum)
        ):
            raise ValueError(f"{path}:{line_number}: sha256 must be 64 hex characters")
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"{path}:{line_number}: size_bytes must be non-negative")

        entries.append(
            {
                "path": path_value,
                "sha256": checksum.lower(),
                "size_bytes": size,
            }
        )
    return entries


def _manifest_entries(manifest: dict) -> list[dict]:
    if manifest.get("status") not in {"audited", "release"}:
        raise ValueError("manifest must be audited or release")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest.sources must not be empty")

    entries: list[dict] = []
    seen_source_ids: set[str] = set()
    seen_paths: set[str] = set()

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{index}] must be an object")
        source_id = source.get("source_id")
        revision = source.get("revision")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError(f"sources[{index}].source_id is required")
        if source_id in seen_source_ids:
            raise ValueError(f"duplicate source_id: {source_id}")
        seen_source_ids.add(source_id)
        if (
            not isinstance(revision, str)
            or not revision.strip()
            or revision.startswith("REPLACE")
        ):
            raise ValueError(f"sources[{index}].revision must be immutable")

        files = source.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError(f"sources[{index}].files must not be empty")
        for file_index, item in enumerate(files):
            where = f"sources[{index}].files[{file_index}]"
            if not isinstance(item, dict):
                raise ValueError(f"{where} must be an object")
            path_value = item.get("path")
            checksum = item.get("sha256")
            size = item.get("size_bytes")
            if not isinstance(path_value, str) or not path_value.strip():
                raise ValueError(f"{where}.path is required")
            if path_value in seen_paths:
                raise ValueError(f"duplicate manifest file path: {path_value}")
            seen_paths.add(path_value)
            if (
                not isinstance(checksum, str)
                or len(checksum) != 64
                or checksum == "REPLACE"
                or any(ch not in "0123456789abcdefABCDEF" for ch in checksum)
            ):
                raise ValueError(f"{where}.sha256 must be verified")
            if not isinstance(size, int) or size < 0:
                raise ValueError(f"{where}.size_bytes must be non-negative")
            entries.append(
                {
                    "path": path_value,
                    "sha256": checksum.lower(),
                    "size_bytes": size,
                    "source_id": source_id,
                    "source_revision": revision,
                }
            )
    return entries


def verify(manifest_path: Path, inventory_path: Path) -> dict:
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")

    manifest_entries = _manifest_entries(manifest)
    inventory_entries = _load_inventory(inventory_path)

    inventory_by_path: dict[str, dict] = {}
    for entry in inventory_entries:
        if entry["path"] in inventory_by_path:
            raise ValueError(f"duplicate inventory file path: {entry['path']}")
        inventory_by_path[entry["path"]] = entry

    manifest_paths = {entry["path"] for entry in manifest_entries}
    inventory_paths = set(inventory_by_path)
    missing = sorted(manifest_paths - inventory_paths)
    extra = sorted(inventory_paths - manifest_paths)

    if missing:
        raise ValueError(
            "manifest references files absent from inventory: " + ", ".join(missing)
        )
    if extra:
        raise ValueError(
            "inventory contains files absent from manifest: " + ", ".join(extra)
        )

    for entry in manifest_entries:
        inventory = inventory_by_path[entry["path"]]
        if entry["sha256"] != inventory["sha256"]:
            raise ValueError(
                f"{entry['path']}: SHA-256 mismatch between manifest and inventory"
            )
        if entry["size_bytes"] != inventory["size_bytes"]:
            raise ValueError(
                f"{entry['path']}: size mismatch between manifest and inventory"
            )

    canonical = json.dumps(
        [
            {
                "path": entry["path"],
                "sha256": entry["sha256"],
                "size_bytes": entry["size_bytes"],
            }
            for entry in sorted(manifest_entries, key=lambda item: item["path"])
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return {
        "schema_version": 1,
        "manifest_id": manifest.get("manifest_id"),
        "status": manifest.get("status"),
        "file_count": len(manifest_entries),
        "inventory_digest": hashlib.sha256(canonical).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("inventory_jsonl", type=Path)
    args = parser.parse_args()

    try:
        result = verify(args.manifest, args.inventory_jsonl)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: manifest/inventory match for {result['manifest_id']} "
        f"({result['file_count']} files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
