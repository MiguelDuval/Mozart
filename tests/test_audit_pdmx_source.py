#!/usr/bin/env python3
"""Tests for deterministic PDMX provenance/subset auditing."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from audit_pdmx_source import audit


FIELDS = [
    "path",
    "metadata",
    "mxl",
    "pdf",
    "mid",
    "license",
    "license_url",
    "license_conflict",
    "subset:no_license_conflict",
    "subset:all_valid",
]


class PdmxAuditTests(unittest.TestCase):
    def write_csv(self, root: Path, rows: list[dict]) -> Path:
        path = root / "PDMX.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def write_subset(self, root: Path, paths: list[str]) -> Path:
        path = root / "no_license_conflict.txt"
        path.write_text("\n".join(paths) + "\n", encoding="utf-8")
        return path

    def test_subset_and_mid_inventory_match(self) -> None:
        rows = [
            {
                "path": "./data/a.json",
                "metadata": "./metadata/a.json",
                "mxl": "N/A",
                "pdf": "N/A",
                "mid": "./mid/a.mid",
                "license": "CC0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "license_conflict": "False",
                "subset:no_license_conflict": "True",
                "subset:all_valid": "False",
            },
            {
                "path": "./data/b.json",
                "metadata": "./metadata/b.json",
                "mxl": "N/A",
                "pdf": "N/A",
                "mid": "N/A",
                "license": "Public Domain",
                "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
                "license_conflict": "False",
                "subset:no_license_conflict": "True",
                "subset:all_valid": "False",
            },
            {
                "path": "./data/c.json",
                "metadata": "./metadata/c.json",
                "mxl": "N/A",
                "pdf": "N/A",
                "mid": "./mid/c.mid",
                "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "license_conflict": "True",
                "subset:no_license_conflict": "False",
                "subset:all_valid": "False",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = self.write_csv(root, rows)
            subset = self.write_subset(root, ["./data/a.json", "./data/b.json"])
            midi = root / "mid"
            midi.mkdir()
            (midi / "a.mid").write_bytes(b"MThd\x00\x00")
            result = audit(csv_path, subset, midi_source=midi)
            self.assertEqual(result["rows"], 3)
            self.assertEqual(result["license_conflicts"], 1)
            self.assertEqual(result["no_license_conflict_rows"], 2)
            self.assertTrue(result["subset_csv_exact_match"])
            self.assertEqual(result["midi_inventory"]["file_count"], 1)
            self.assertTrue(result["midi_inventory"]["csv_mid_exact_match"])
            self.assertTrue(result["midi_inventory"]["no_license_conflict_mid_all_present"])

    def test_subset_mismatch_is_reported(self) -> None:
        row = {
            "path": "./data/a.json",
            "metadata": "./metadata/a.json",
            "mxl": "N/A",
            "pdf": "N/A",
            "mid": "./mid/a.mid",
            "license": "CC0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "license_conflict": "False",
            "subset:no_license_conflict": "True",
            "subset:all_valid": "False",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = self.write_csv(root, [row])
            subset = self.write_subset(root, [])
            result = audit(csv_path, subset)
            self.assertFalse(result["subset_csv_exact_match"])
            self.assertEqual(result["csv_subset_rows_missing_from_subset_file"], 1)

    def test_missing_recommended_license_metadata_is_reported(self) -> None:
        row = {
            "path": "./data/a.json",
            "metadata": "./metadata/a.json",
            "mxl": "N/A",
            "pdf": "N/A",
            "mid": "./mid/a.mid",
            "license": "N/A",
            "license_url": "N/A",
            "license_conflict": "False",
            "subset:no_license_conflict": "True",
            "subset:all_valid": "False",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = self.write_csv(root, [row])
            subset = self.write_subset(root, ["./data/a.json"])
            result = audit(csv_path, subset)
            self.assertEqual(result["recommended_rows_missing_license_metadata"], 1)

    def test_tar_inventory_is_supported(self) -> None:
        row = {
            "path": "./data/a.json",
            "metadata": "./metadata/a.json",
            "mxl": "N/A",
            "pdf": "N/A",
            "mid": "./mid/a.mid",
            "license": "CC0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "license_conflict": "False",
            "subset:no_license_conflict": "True",
            "subset:all_valid": "False",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = self.write_csv(root, [row])
            subset = self.write_subset(root, ["./data/a.json"])
            source = root / "mid.tar.gz"
            payload = b"MThd\x00\x00"
            with tarfile.open(source, "w:gz") as tf:
                info = tarfile.TarInfo("mid/a.mid")
                info.size = len(payload)
                tf.addfile(info, io.BytesIO(payload))
                directory = tarfile.TarInfo("mid/subdir")
                directory.type = tarfile.DIRTYPE
                tf.addfile(directory)
            result = audit(csv_path, subset, midi_source=source)
            expected = hashlib.sha256(payload).hexdigest()
            self.assertTrue(result["midi_inventory"]["csv_mid_exact_match"])
            self.assertTrue(result["midi_inventory"]["no_license_conflict_mid_all_present"])
            self.assertEqual(result["midi_inventory"]["file_count"], 1)
            self.assertEqual(
                result["midi_inventory"]["inventory_sha256"],
                hashlib.sha256(
                    json.dumps(
                        [{"path": "mid/a.mid", "sha256": expected, "size_bytes": len(payload)}],
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
