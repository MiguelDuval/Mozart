#!/usr/bin/env python3
"""Verify dataset-manifest file paths, sizes, and SHA-256 digests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def _read_manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("manifest root must be an object")
    return value


def _safe_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("dataset file path must be a non-empty string")
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"dataset file path must be relative: {value}")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"dataset file path escapes dataset root: {value}")
    return path


def verify(manifest_path: Path, dataset_root: Path) -> dict:
    manifest = _read_manifest(manifest_path)
    status = manifest.get("status")
    if status not in {"audited", "release"}:
        raise ValueError(
            "file verification requires an audited or release manifest"
        )

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest.sources must contain at least one source")

    checked_files = 0
    total_bytes = 0
    root_path = dataset_root.resolve()

    for source_index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{source_index}] must be an object")

        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError(f"sources[{source_index}].source_id is required")

        revision = source.get("revision")
        if (
            not isinstance(revision, str)
            or not revision.strip()
            or revision.startswith("REPLACE")
        ):
            raise ValueError(
                f"sources[{source_index}].revision must be immutable"
            )

        files = source.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError(f"sources[{source_index}].files must not be empty")

        for file_index, item in enumerate(files):
            where = f"sources[{source_index}].files[{file_index}]"
            if not isinstance(item, dict):
                raise ValueError(f"{where} must be an object")

            relative = _safe_relative_path(item.get("path"))
            expected_sha = item.get("sha256")
            expected_size = item.get("size_bytes")

            if (
                not isinstance(expected_sha, str)
                or len(expected_sha) != 64
                or expected_sha == "REPLACE"
            ):
                raise ValueError(f"{where}.sha256 must be verified")

            if not isinstance(expected_size, int) or expected_size < 0:
                raise ValueError(
                    f"{where}.size_bytes must be non-negative"
                )

            file_path = (dataset_root / relative).resolve()
            try:
                file_path.relative_to(root_path)
            except ValueError as exc:
                raise ValueError(f"{where} escapes dataset root") from exc

            if not file_path.is_file():
                raise ValueError(f"dataset file does not exist: {relative}")

            actual_size = file_path.stat().st_size
            if actual_size != expected_size:
                raise ValueError(
                    f"{relative}: size mismatch "
                    f"expected={expected_size} actual={actual_size}"
                )

            digest = hashlib.sha256()
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual_sha = digest.hexdigest()

            if actual_sha.lower() != expected_sha.lower():
                raise ValueError(
                    f"{relative}: SHA-256 mismatch "
                    f"expected={expected_sha} actual={actual_sha}"
                )

            checked_files += 1
            total_bytes += actual_size

    return {
        "schema_version": 1,
        "manifest_id": manifest.get("manifest_id"),
        "status": status,
        "checked_files": checked_files,
        "total_bytes": total_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dataset_root", type=Path)
    args = parser.parse_args()

    try:
        result = verify(args.manifest, args.dataset_root)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: verified {result['checked_files']} dataset files "
        f"({result['total_bytes']} bytes) for {result['manifest_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
