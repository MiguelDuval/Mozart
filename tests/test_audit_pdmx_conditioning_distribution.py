#!/usr/bin/env python3
"""Tests for the deterministic real-data PDMX conditioning preflight."""

from __future__ import annotations

import csv
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from audit_pdmx_conditioning_distribution import audit


FIELDS = [
    "path",
    "mid",
    "license",
    "license_url",
    "subset:no_license_conflict",
]


def vlq(value: int) -> bytes:
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.reverse()
    return bytes(parts)


def smf_fixture() -> bytes:
    events = (
        bytes.fromhex("00 90 3C 64")
        + vlq(480)
        + bytes.fromhex("80 3C 00")
        + bytes.fromhex("00 FF 2F 00")
    )
    header = b"MThd" + bytes.fromhex("00 00 00 06 00 00 00 01 01 E0")
    track = b"MTrk" + len(events).to_bytes(4, "big") + events
    return header + track


class PdmxConditioningDistributionTests(unittest.TestCase):
    def _write_csv(self, root: Path) -> Path:
        path = root / "PDMX.csv"
        rows = [
            {
                "path": "./data/a.json",
                "mid": "./mid/a.mid",
                "license": "CC0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "subset:no_license_conflict": "True",
            },
            {
                "path": "./data/b.json",
                "mid": "N/A",
                "license": "CC0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "subset:no_license_conflict": "True",
            },
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _write_subset(self, root: Path) -> Path:
        path = root / "no_license_conflict.txt"
        path.write_text("./data/a.json\n./data/b.json\n", encoding="utf-8")
        return path

    def _write_tar(self, root: Path) -> Path:
        path = root / "mid.tar.gz"
        payload = smf_fixture()
        with tarfile.open(path, "w:gz") as archive:
            directory = tarfile.TarInfo("mid")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)

            info = tarfile.TarInfo("mid/a.mid")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        return path

    def test_rows_without_midi_are_excluded_from_candidate_sample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = audit(
                self._write_csv(root),
                self._write_subset(root),
                self._write_tar(root),
                sample_size=32,
            )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["selection"]["csv_rows"], 2)
        self.assertEqual(result["selection"]["candidate_count"], 1)
        self.assertEqual(result["selection"]["selected_count"], 1)
        self.assertEqual(result["results"]["successful_samples"], 1)
        self.assertEqual(result["results"]["failed_samples"], 0)
        self.assertEqual(result["results"]["missing_from_archive"], 0)
        self.assertEqual(
            result["results"]["controls"]["swing"]["status"],
            "NOT_MEASURED",
        )

    def test_sampling_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = self._write_csv(root)
            subset_path = self._write_subset(root)
            tar_path = self._write_tar(root)
            left = audit(csv_path, subset_path, tar_path, sample_size=1)
            right = audit(csv_path, subset_path, tar_path, sample_size=1)

        self.assertEqual(left["selection"], right["selection"])
        self.assertEqual(left["results"], right["results"])


if __name__ == "__main__":
    unittest.main()
