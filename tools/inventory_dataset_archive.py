#!/usr/bin/env python3
"""Build a deterministic SHA-256 inventory for a TAR/TAR.GZ dataset archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
import tarfile
from pathlib import Path


def _safe_member_path(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("archive member path must be a non-empty string")
    normalized = posixpath.normpath(name)
    if normalized in {"", "."} or normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"unsafe archive member path: {name}")
    if any(part == ".." for part in normalized.split("/")):
        raise ValueError(f"unsafe archive member path: {name}")
    return normalized


def _canonical_bytes(entries: list[dict]) -> bytes:
    return json.dumps(
        sorted(entries, key=lambda item: item["path"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def inventory(
    archive: Path,
    *,
    extension: str | None = None,
    expected_count: int | None = None,
    output: Path | None = None,
) -> dict:
    entries: list[dict] = []
    seen_paths: set[str] = set()
    extension = extension.lower() if extension else None

    try:
        with tarfile.open(archive, "r:*") as tf:
            for member in tf:
                if not member.isfile():
                    raise ValueError(f"archive contains non-regular member: {member.name}")

                member_path = _safe_member_path(member.name)
                if member_path in seen_paths:
                    raise ValueError(f"duplicate archive member path: {member_path}")
                seen_paths.add(member_path)

                if extension and not member_path.lower().endswith(extension):
                    raise ValueError(
                        f"archive member does not match required extension "
                        f"{extension}: {member_path}"
                    )

                handle = tf.extractfile(member)
                if handle is None:
                    raise ValueError(f"cannot read archive member: {member_path}")

                digest = hashlib.sha256()
                size = 0
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)

                entries.append(
                    {
                        "path": member_path,
                        "sha256": digest.hexdigest(),
                        "size_bytes": size,
                    }
                )
    except (OSError, tarfile.TarError) as exc:
        raise ValueError(f"cannot read archive {archive}: {exc}") from exc

    entries.sort(key=lambda item: item["path"])
    if expected_count is not None and len(entries) != expected_count:
        raise ValueError(
            f"archive member count mismatch: expected={expected_count} actual={len(entries)}"
        )

    digest = hashlib.sha256(_canonical_bytes(entries)).hexdigest()

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                handle.write(
                    json.dumps(
                        entry,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

    return {
        "schema_version": 1,
        "archive": str(archive),
        "file_count": len(entries),
        "total_bytes": sum(entry["size_bytes"] for entry in entries),
        "inventory_sha256": digest,
        "output": str(output) if output else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--extension", help="Require every regular member to use this suffix, e.g. .mid")
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--output", type=Path, help="Write canonical JSONL inventory to this path")
    args = parser.parse_args()

    try:
        result = inventory(
            args.archive,
            extension=args.extension,
            expected_count=args.expected_count,
            output=args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: {result['file_count']} files, {result['total_bytes']} bytes, "
        f"inventory_sha256={result['inventory_sha256']}"
    )
    if result["output"]:
        print(f"inventory={result['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
