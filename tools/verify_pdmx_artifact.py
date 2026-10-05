#!/usr/bin/env python3
"""Verify a downloaded PDMX acquisition artifact against its pinned manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def hashes(path: Path) -> dict[str, str | int]:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            md5.update(chunk)
            sha256.update(chunk)
            size += len(chunk)
    return {
        "size_bytes": size,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported PDMX acquisition manifest schema")
    artifacts = data.get("published_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("manifest has no published_artifacts")
    return data


def verify(file_path: Path, manifest_path: Path, artifact_name: str, output: Path | None = None) -> dict:
    manifest = load_manifest(manifest_path)
    candidates = [
        item for item in manifest["published_artifacts"]
        if item.get("name") == artifact_name
    ]
    if len(candidates) != 1:
        raise ValueError(f"artifact not uniquely defined in manifest: {artifact_name}")
    expected = candidates[0]

    actual = hashes(file_path)
    expected_md5 = expected.get("md5", "").lower()
    if actual["md5"] != expected_md5:
        raise ValueError(
            f"MD5 mismatch for {artifact_name}: "
            f"expected={expected_md5} actual={actual['md5']}"
        )

    result = {
        "schema_version": 1,
        "artifact": artifact_name,
        "path": str(file_path),
        "manifest": str(manifest_path),
        "verified": True,
        "md5": actual["md5"],
        "sha256": actual["sha256"],
        "size_bytes": actual["size_bytes"],
        "published_size": expected.get("size_bytes_decimal") or expected.get("size_display"),
    }

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--name", required=True, help="Exact manifest artifact name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        result = verify(args.artifact, args.manifest, args.name, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(
        f"PASS: {result['artifact']} "
        f"size={result['size_bytes']} "
        f"md5={result['md5']} "
        f"sha256={result['sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
