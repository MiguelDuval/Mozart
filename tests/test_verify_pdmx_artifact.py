#!/usr/bin/env python3
"""Tests for PDMX artifact checksum verification."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verify_pdmx_artifact import verify


class PdmxArtifactTests(unittest.TestCase):
    def manifest(self, root: Path, md5: str) -> Path:
        path = root / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "published_artifacts": [
                        {
                            "name": "fixture.bin",
                            "md5": md5,
                            "size_display": "fixture",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_matching_md5_returns_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "fixture.bin"
            artifact.write_bytes(b"mozart-pdmx")
            import hashlib
            manifest = self.manifest(root, hashlib.md5(b"mozart-pdmx").hexdigest())
            result = verify(artifact, manifest, "fixture.bin")
            self.assertTrue(result["verified"])
            self.assertEqual(result["sha256"], hashlib.sha256(b"mozart-pdmx").hexdigest())

    def test_mismatching_md5_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "fixture.bin"
            artifact.write_bytes(b"mozart-pdmx")
            manifest = self.manifest(root, "0" * 32)
            with self.assertRaises(ValueError):
                verify(artifact, manifest, "fixture.bin")


if __name__ == "__main__":
    unittest.main()
