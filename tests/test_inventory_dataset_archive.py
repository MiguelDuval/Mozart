#!/usr/bin/env python3
"""Tests for deterministic TAR archive inventory generation."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from inventory_dataset_archive import inventory


class InventoryDatasetArchiveTests(unittest.TestCase):
    def _make_archive(self, root: Path, *, include_extra: bool = False) -> Path:
        archive = root / "fixture.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            for name, payload in (
                ("b.mid", b"bbb"),
                ("a.mid", b"aaa"),
            ):
                source = root / name
                source.write_bytes(payload)
                tf.add(source, arcname=name)
            if include_extra:
                source = root / "readme.txt"
                source.write_text("metadata", encoding="utf-8")
                tf.add(source, arcname="readme.txt")
        return archive

    def test_inventory_is_deterministic_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._make_archive(root)
            output = root / "inventory.jsonl"

            result = inventory(
                archive,
                extension=".mid",
                expected_count=2,
                output=output,
            )

            entries = [
                {"path": "a.mid", "sha256": hashlib.sha256(b"aaa").hexdigest(), "size_bytes": 3},
                {"path": "b.mid", "sha256": hashlib.sha256(b"bbb").hexdigest(), "size_bytes": 3},
            ]
            expected = hashlib.sha256(
                json.dumps(
                    entries,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()

            self.assertEqual(result["inventory_sha256"], expected)
            self.assertEqual(result["file_count"], 2)
            self.assertEqual(output.read_text(encoding="utf-8").count("\n"), 2)

    def test_wrong_count_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._make_archive(root)
            with self.assertRaises(ValueError):
                inventory(archive, extension=".mid", expected_count=3)

    def test_unexpected_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._make_archive(root, include_extra=True)
            with self.assertRaises(ValueError):
                inventory(archive, extension=".mid")

    def test_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as tf:
                info = tarfile.TarInfo("../escape.mid")
                payload = b"bad"
                info.size = len(payload)
                tf.addfile(info, io.BytesIO(payload))
            with self.assertRaises(ValueError):
                inventory(archive, extension=".mid")


if __name__ == "__main__":
    unittest.main()
