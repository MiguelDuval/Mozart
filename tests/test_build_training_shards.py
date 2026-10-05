#!/usr/bin/env python3
"""Tests for deterministic Mozart training shard construction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_training_shards import (
    _prepare_training_provenance,
    _resolve_manifest_sha256,
    _stats,
    read_jsonl,
    validate_records,
    write_shards,
)
from manifest_digest import digest as manifest_digest


def record(
    source_id: str,
    source_revision: str,
    split: str,
    source_path: str,
    *,
    style: str = "electronic",
    role: str = "bass",
) -> dict:
    return {
        "schema_version": 1,
        "source_id": source_id,
        "source_revision": source_revision,
        "source_path": source_path,
        "vocabulary_id": "mozart-midi-events-v1",
        "vocabulary_size": 512,
        "conditioning_vocabulary_id": "mozart-conditioning-v1",
        "conditioning": {
            "style": style,
            "substyle": "techno",
            "mood": "driving",
            "rhythm": "straight",
            "role": role,
        },
        "performance_controls": {
            "density": 0.25,
            "energy": 0.5,
            "syncopation": 0.0,
            "swing": 0.0,
            "variation": 0.0,
        },
        "music": {
            "length_bars": 4,
            "note_event_count": 1,
            "controller_event_count": 0,
            "max_start_step_polyphony": 1,
            "pitch_histogram": [1 if index == 60 else 0 for index in range(128)],
            "velocity_bin_histogram": [1] + [0] * 31,
        },
        "tokens": [1, 16, 92, 185, 256, 215, 2],
        "split": split,
    }


class BuildTrainingShardsTests(unittest.TestCase):
    def test_source_group_cannot_cross_splits(self) -> None:
        records = [
            record("song-a", "rev-1", "train", "a.mid"),
            record("song-a", "rev-1", "validation", "a-window.mid"),
        ]
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_shards_are_deterministic_and_bounded(self) -> None:
        records = [
            record("song-b", "rev-1", "train", "b.mid"),
            record("song-a", "rev-1", "train", "a.mid", role="chords"),
        ]
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            left_dir = Path(left)
            right_dir = Path(right)
            write_shards(records, left_dir, max_records_per_shard=1)
            write_shards(list(reversed(records)), right_dir, max_records_per_shard=1)

            left_payloads = sorted(
                path.read_text(encoding="utf-8")
                for path in left_dir.glob("train-*.jsonl")
            )
            right_payloads = sorted(
                path.read_text(encoding="utf-8")
                for path in right_dir.glob("train-*.jsonl")
            )
            self.assertEqual(left_payloads, right_payloads)

            first = json.loads(
                (left_dir / "train-00000.jsonl").read_text(encoding="utf-8")
            )
            self.assertEqual(first["source_id"], "song-a")

    def test_statistics_capture_split_and_conditioning_counts(self) -> None:
        records = [
            record("song-a", "rev-1", "train", "a.mid"),
            record("song-b", "rev-1", "test", "b.mid", role="chords"),
        ]
        records[1]["performance_controls"]["energy"] = 1.0
        records[1]["performance_controls"]["variation"] = 0.5
        stats = _stats(records, "abc123")
        self.assertEqual(stats["record_count"], 2)
        self.assertEqual(stats["source_group_count"], 2)
        self.assertEqual(stats["musical_event_statistics"]["note_event_count"], 2)
        self.assertEqual(stats["musical_event_statistics"]["controller_event_count"], 0)
        self.assertEqual(stats["musical_event_statistics"]["max_start_step_polyphony"], 1)
        self.assertEqual(
            sum(stats["musical_event_statistics"]["pitch_histogram"]),
            2,
        )
        self.assertEqual(
            sum(stats["musical_event_statistics"]["velocity_bin_histogram"]),
            2,
        )
        self.assertEqual(
            stats["split_counts"],
            {"train": 1, "validation": 0, "test": 1},
        )
        self.assertEqual(
            stats["conditioning"]["role"],
            {"bass": 1, "chords": 1},
        )
        self.assertAlmostEqual(stats["performance_controls"]["energy"]["min"], 0.5)
        self.assertAlmostEqual(stats["performance_controls"]["energy"]["max"], 1.0)
        self.assertAlmostEqual(stats["performance_controls"]["energy"]["mean"], 0.75)
        self.assertAlmostEqual(stats["performance_controls"]["energy"]["non_zero_fraction"], 1.0)
        self.assertAlmostEqual(stats["performance_controls"]["variation"]["max"], 0.5)
        self.assertEqual(
            stats["reproducibility"]["manifest_sha256"],
            "abc123",
        )

    def test_statistics_include_manifest_provenance(self) -> None:
        records = [
            record("song-a", "rev-1", "train", "a.mid"),
            record("song-b", "rev-2", "test", "b.mid", role="chords"),
        ]
        manifest = {
            "manifest_id": "dataset-v1",
            "status": "audited",
            "sources": [
                {
                    "source_id": "song-a",
                    "license": {
                        "spdx_id": "CC-BY-4.0",
                        "commercial_use": "allowed",
                        "redistribution": "allowed",
                        "attribution": "required",
                    },
                    "provenance": {"provider": "provider-a"},
                },
                {
                    "source_id": "song-b",
                    "license": {
                        "spdx_id": "CC0-1.0",
                        "commercial_use": "allowed",
                        "redistribution": "allowed",
                        "attribution": "not-required",
                    },
                    "provenance": {"provider": "provider-b"},
                },
            ],
        }
        stats = _stats(records, "abc123", manifest)
        self.assertEqual(stats["sources"]["record_counts"], {
            "song-a\0rev-1": 1,
            "song-b\0rev-2": 1,
        })
        self.assertEqual(stats["provenance"]["manifest_id"], "dataset-v1")
        self.assertEqual(stats["provenance"]["source_count"], 2)
        self.assertEqual(
            stats["provenance"]["license_spdx_counts"],
            {"CC-BY-4.0": 1, "CC0-1.0": 1},
        )
        self.assertEqual(
            stats["provenance"]["commercial_use_counts"],
            {"allowed": 2},
        )
        self.assertEqual(
            stats["provenance"]["redistribution_counts"],
            {"allowed": 2},
        )
        self.assertEqual(
            stats["provenance"]["attribution_counts"],
            {"not-required": 1, "required": 1},
        )
        self.assertEqual(
            stats["provenance"]["unrepresented_manifest_sources"],
            [],
        )

    def test_statistics_reject_manifest_source_coverage_gap(self) -> None:
        records = [record("song-a", "rev-1", "train", "a.mid")]
        manifest = {
            "manifest_id": "dataset-v1",
            "status": "audited",
            "sources": [
                {
                    "source_id": "other-source",
                    "license": {
                        "spdx_id": "CC0-1.0",
                        "commercial_use": "allowed",
                        "redistribution": "allowed",
                        "attribution": "not-required",
                    },
                    "provenance": {"provider": "provider"},
                }
            ],
        }
        with self.assertRaises(ValueError):
            _stats(records, "abc123", manifest)

    def test_invalid_conditioning_slug_is_rejected(self) -> None:
        item = record("song-a", "rev-1", "train", "a.mid")
        item["conditioning"]["mood"] = "not_a_real_mood"
        with self.assertRaises(ValueError):
            validate_records([item])

    def test_missing_conditioning_vocabulary_is_rejected(self) -> None:
        item = record("song-a", "rev-1", "train", "a.mid")
        del item["conditioning_vocabulary_id"]
        with self.assertRaises(ValueError):
            validate_records([item])

    def _production_manifest(self) -> dict:
        return {
            "schema_version": 1,
            "manifest_id": "dataset-v1",
            "status": "audited",
            "license_policy": "commercial-compatible-only",
            "project_vocabulary_id": "mozart-midi-events-v1",
            "sources": [
                {
                    "source_id": "song-a",
                    "name": "Song A",
                    "locator": "fixture://song-a",
                    "revision": "rev-1",
                    "license": {
                        "spdx_id": "CC0-1.0",
                        "commercial_use": "allowed",
                        "redistribution": "allowed",
                        "attribution": "not-required",
                    },
                    "files": [
                        {
                            "path": "source/a.mid",
                            "sha256": "1" * 64,
                            "size_bytes": 7,
                        }
                    ],
                    "provenance": {
                        "provider": "fixture",
                        "acquisition_date": "2026-09-29",
                        "rights_evidence": "fixture-rights-v1",
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
                "max_events_per_example": 4096,
            },
            "examples": {
                "min_bars": 4,
                "max_bars": 16,
                "context_length_tokens": "fixture",
                "max_generated_tokens": "fixture",
            },
        }

    def test_provenance_gate_accepts_exact_manifest_inventory_and_records(self) -> None:
        records = [record("song-a", "rev-1", "train", "source/a.mid")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            inventory_path = root / "inventory.jsonl"
            manifest = self._production_manifest()
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True),
                encoding="utf-8",
            )
            inventory_path.write_text(
                json.dumps(
                    {
                        "path": "source/a.mid",
                        "sha256": "1" * 64,
                        "size_bytes": 7,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            returned_manifest, returned_digest = _prepare_training_provenance(
                records,
                manifest_path,
                inventory_path,
                None,
            )

            self.assertEqual(returned_manifest["manifest_id"], "dataset-v1")
            self.assertEqual(returned_digest, manifest_digest(manifest_path))

    def test_provenance_gate_rejects_template_manifest(self) -> None:
        records = [record("song-a", "rev-1", "train", "source/a.mid")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            inventory_path = root / "inventory.jsonl"
            manifest = self._production_manifest()
            manifest["status"] = "template"
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True),
                encoding="utf-8",
            )
            inventory_path.write_text(
                json.dumps(
                    {
                        "path": "source/a.mid",
                        "sha256": "1" * 64,
                        "size_bytes": 7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "audited or release"):
                _prepare_training_provenance(
                    records, manifest_path, inventory_path, None
                )

    def test_provenance_gate_rejects_record_outside_inventory(self) -> None:
        records = [record("song-a", "rev-1", "train", "source/missing.mid")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            inventory_path = root / "inventory.jsonl"
            manifest_path.write_text(
                json.dumps(self._production_manifest(), sort_keys=True),
                encoding="utf-8",
            )
            inventory_path.write_text(
                json.dumps(
                    {
                        "path": "source/a.mid",
                        "sha256": "1" * 64,
                        "size_bytes": 7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "source_path .* absent"):
                _prepare_training_provenance(
                    records, manifest_path, inventory_path, None
                )

    def test_provenance_gate_rejects_source_revision_mismatch(self) -> None:
        records = [record("song-a", "rev-2", "train", "source/a.mid")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            inventory_path = root / "inventory.jsonl"
            manifest_path.write_text(
                json.dumps(self._production_manifest(), sort_keys=True),
                encoding="utf-8",
            )
            inventory_path.write_text(
                json.dumps(
                    {
                        "path": "source/a.mid",
                        "sha256": "1" * 64,
                        "size_bytes": 7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "source_revision"):
                _prepare_training_provenance(
                    records, manifest_path, inventory_path, None
                )

    def test_provenance_gate_rejects_inventory_mismatch(self) -> None:
        records = [record("song-a", "rev-1", "train", "source/a.mid")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            inventory_path = root / "inventory.jsonl"
            manifest_path.write_text(
                json.dumps(self._production_manifest(), sort_keys=True),
                encoding="utf-8",
            )
            inventory_path.write_text(
                json.dumps(
                    {
                        "path": "source/a.mid",
                        "sha256": "2" * 64,
                        "size_bytes": 7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                _prepare_training_provenance(
                    records, manifest_path, inventory_path, None
                )

    def test_manifest_path_produces_canonical_digest(self) -> None:
        manifest = {
            "manifest_id": "dataset-v1",
            "status": "audited",
            "sources": [{"source_id": "source-a"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(manifest, sort_keys=True),
                encoding="utf-8",
            )
            self.assertEqual(
                _resolve_manifest_sha256(path, None),
                manifest_digest(path),
            )

    def test_matching_explicit_manifest_digest_is_accepted(self) -> None:
        manifest = {
            "manifest_id": "dataset-v1",
            "status": "audited",
            "sources": [{"source_id": "source-a"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(manifest, sort_keys=True),
                encoding="utf-8",
            )
            expected = manifest_digest(path)
            self.assertEqual(
                _resolve_manifest_sha256(path, expected.upper()),
                expected,
            )

    def test_mismatching_explicit_manifest_digest_is_rejected(self) -> None:
        manifest = {
            "manifest_id": "dataset-v1",
            "status": "audited",
            "sources": [{"source_id": "source-a"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                json.dumps(manifest, sort_keys=True),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "manifest SHA-256 does not match --manifest-sha256",
            ):
                _resolve_manifest_sha256(path, "0" * 64)

    def test_jsonl_round_trip(self) -> None:
        records = [record("song-a", "rev-1", "train", "a.mid")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.jsonl"
            path.write_text(
                json.dumps(records[0], sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(read_jsonl(path), records)


if __name__ == "__main__":
    unittest.main()
