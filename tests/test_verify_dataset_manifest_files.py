#!/usr/bin/env python3
"""Tests for dataset-manifest file verification."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verify_dataset_manifest_files import verify


def manifest_for(
    relative_path: str,
    sha256: str,
    size_bytes: int,
    *,
    status: str = "audited",
) -> dict:
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
                "revision": "fixture-rev-1",
                "license": {
                    "spdx_id": "CC0-1.0",
                    "commercial_use": "allowed",
                    "redistribution": "allowed",
                    "attribution": "not-required",
                },
                "files": [
                    {
                        "path": relative_path,
                        "sha256": sha256,
                        "size_bytes": size_bytes,
                    }
                ],
                "provenance": {
                    "provider": "test",
                    "acquisition_date": "2026-09-29",
                    "rights_evidence": "fixture",
                },
            }
        ],
        "splits": {
            "train": "train.jsonl",
            "validation": "validation.jsonl",
            "test": "test.jsonl",
        },
        "normalization": {
            "revision": "mozart-midi-normalization-v1",
            "ticks_per_quarter_policy": "resample_to_480",
            "tempo_policy": "preserve_tempo_events",
            "meter_policy": "preserve_supported_time_signatures",
            "channel_policy": "preserve_0_15; drums_use_channel_9",
            "note_policy": "drop_invalid; clamp_never",
            "velocity_policy": "map_to_32_bins",
            "duration_policy": "quantize_to_1_16_beat_grid",
            "time_shift_policy": "encode_using_mozart_64_bin_time_shifts",
            "controller_policy": "encode_0_127_controller_and_32_value_bins",
            "deduplication": "canonicalize_identical_events",
            "max_events_per_example": 4096,
        },
        "examples": {
            "min_bars": 4,
            "max_bars": 16,
            "context_length_tokens": "fixture",
            "max_generated_tokens": "fixture",
        },
    }


class VerifyDatasetManifestFilesTests(unittest.TestCase):
    def test_verified_file_passes(self) -> None:
        payload = b"fixture-midi-bytes"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "source" / "fixture.mid"
            file_path.parent.mkdir()
            file_path.write_bytes(payload)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(manifest_for("source/fixture.mid", digest, len(payload))),
                encoding="utf-8",
            )

            result = verify(manifest, root)
            self.assertEqual(result["checked_files"], 1)
            self.assertEqual(result["total_bytes"], len(payload))

    def test_sha_mismatch_is_rejected(self) -> None:
        payload = b"fixture-midi-bytes"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "fixture.mid"
            file_path.write_bytes(payload)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(manifest_for("fixture.mid", "0" * 64, len(payload))),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                verify(manifest, root)

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(manifest_for("../outside.mid", "0" * 64, 0)),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                verify(manifest, root)

    def test_template_manifest_is_not_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    manifest_for("fixture.mid", "0" * 64, 0, status="template")
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                verify(manifest, root)


if __name__ == "__main__":
    unittest.main()
