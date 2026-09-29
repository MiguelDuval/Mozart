#!/usr/bin/env python3
"""Tests for exact MIDI inventory ↔ audited manifest matching."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verify_manifest_inventory import verify


def make_manifest(path: str, sha: str, size: int, *, status: str = "audited") -> dict:
    return {
        "schema_version": 1,
        "manifest_id": "fixture-manifest",
        "status": status,
        "license_policy": "commercial-compatible-only",
        "project_vocabulary_id": "mozart-midi-events-v1",
        "sources": [
            {
                "source_id": "fixture-source",
                "name": "Fixture",
                "locator": "fixture://local",
                "revision": "rev-1",
                "license": {
                    "spdx_id": "CC0-1.0",
                    "commercial_use": "allowed",
                    "redistribution": "allowed",
                    "attribution": "not-required",
                },
                "files": [{"path": path, "sha256": sha, "size_bytes": size}],
                "provenance": {
                    "provider": "test",
                    "acquisition_date": "2026-09-29",
                    "rights_evidence": "fixture",
                },
            }
        ],
        "splits": {
            "train": "train",
            "validation": "validation",
            "test": "test",
        },
        "normalization": {
            "revision": "mozart-midi-normalization-v1",
            "max_events_per_example": 4096,
        },
        "examples": {
            "min_bars": 4,
            "max_bars": 16,
            "context_length_tokens": "fixture",
            "max_generated_tokens": "fixture",
        },
    }


def write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in entries),
        encoding="utf-8",
    )


class VerifyManifestInventoryTests(unittest.TestCase):
    def test_exact_match_passes(self) -> None:
        payload = b"fixture"
        sha = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            inventory = root / "inventory.jsonl"
            manifest.write_text(
                json.dumps(make_manifest("a.mid", sha, len(payload))),
                encoding="utf-8",
            )
            write_jsonl(
                inventory,
                [{"path": "a.mid", "sha256": sha, "size_bytes": len(payload)}],
            )

            result = verify(manifest, inventory)
            self.assertEqual(result["file_count"], 1)
            self.assertEqual(result["status"], "audited")
            self.assertEqual(len(result["inventory_digest"]), 64)

    def test_missing_inventory_entry_is_rejected(self) -> None:
        sha = hashlib.sha256(b"fixture").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            inventory = root / "inventory.jsonl"
            manifest.write_text(
                json.dumps(make_manifest("a.mid", sha, 7)),
                encoding="utf-8",
            )
            write_jsonl(inventory, [])
            with self.assertRaises(ValueError):
                verify(manifest, inventory)

    def test_extra_inventory_entry_is_rejected(self) -> None:
        sha = hashlib.sha256(b"fixture").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            inventory = root / "inventory.jsonl"
            manifest.write_text(
                json.dumps(make_manifest("a.mid", sha, 7)),
                encoding="utf-8",
            )
            write_jsonl(
                inventory,
                [
                    {"path": "a.mid", "sha256": sha, "size_bytes": 7},
                    {"path": "extra.mid", "sha256": sha, "size_bytes": 7},
                ],
            )
            with self.assertRaises(ValueError):
                verify(manifest, inventory)

    def test_duplicate_manifest_file_path_is_rejected(self) -> None:
        sha = hashlib.sha256(b"fixture").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_manifest("a.mid", sha, 7)
            manifest["sources"].append(
                {
                    "source_id": "second",
                    "name": "Second",
                    "locator": "fixture://second",
                    "revision": "rev-2",
                    "license": {
                        "spdx_id": "CC0-1.0",
                        "commercial_use": "allowed",
                        "redistribution": "allowed",
                        "attribution": "not-required",
                    },
                    "files": [{"path": "a.mid", "sha256": sha, "size_bytes": 7}],
                    "provenance": {
                        "provider": "test",
                        "acquisition_date": "2026-09-29",
                        "rights_evidence": "fixture",
                    },
                }
            )
            manifest_path = root / "manifest.json"
            inventory = root / "inventory.jsonl"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            write_jsonl(
                inventory,
                [{"path": "a.mid", "sha256": sha, "size_bytes": 7}],
            )
            with self.assertRaises(ValueError):
                verify(manifest_path, inventory)


if __name__ == "__main__":
    unittest.main()
