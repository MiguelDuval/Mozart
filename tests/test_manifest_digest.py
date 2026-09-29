#!/usr/bin/env python3
"""Tests for deterministic manifest digesting."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from manifest_digest import digest


class ManifestDigestTests(unittest.TestCase):
    def test_digest_is_stable_and_ignores_self_checksum(self) -> None:
        base = {
            "schema_version": 1,
            "manifest_id": "fixture",
            "status": "template",
            "sources": [{"source_id": "a"}],
            "checksums": {"manifest_sha256": "NOT_COMPUTED_IN_TEMPLATE"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(base), encoding="utf-8")
            first = digest(path)

            base["checksums"]["manifest_sha256"] = first
            path.write_text(
                json.dumps(base, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            second = digest(path)

            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)

    def test_semantic_change_changes_digest(self) -> None:
        base = {
            "schema_version": 1,
            "manifest_id": "fixture",
            "status": "template",
            "sources": [{"source_id": "a"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(base), encoding="utf-8")
            first = digest(path)
            base["manifest_id"] = "fixture-2"
            path.write_text(json.dumps(base), encoding="utf-8")
            second = digest(path)
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
