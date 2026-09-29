#!/usr/bin/env python3
"""Compute a canonical SHA-256 digest for a Mozart dataset manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical_manifest_bytes(manifest: object) -> bytes:
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")

    copy = dict(manifest)
    checksums = copy.get("checksums")
    if isinstance(checksums, dict):
        checksums = dict(checksums)
        checksums["manifest_sha256"] = "SELF"
        copy["checksums"] = checksums
    else:
        copy["checksums"] = {"manifest_sha256": "SELF"}

    return (
        json.dumps(
            copy,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def digest(path: Path) -> str:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest {path}: {exc}") from exc
    return hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expect")
    args = parser.parse_args()

    try:
        value = digest(args.manifest)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(value)
    if args.expect and value.lower() != args.expect.lower():
        print("ERROR: manifest digest does not match --expect")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
