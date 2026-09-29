#!/usr/bin/env python3
"""Tests for deterministic Mozart training shard construction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_training_shards import _stats, read_jsonl, validate_records, write_shards


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
        "conditioning": {
            "style": style,
            "substyle": "techno",
            "mood": "driving",
            "rhythm": "straight",
            "role": role,
        },
        "music": {"length_bars": 4},
        "tokens": [1, 16, 92, 216, 256, 215, 2],
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
            record("song-a", "rev-1", "train", "a.mid", role="chord"),
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
            record("song-b", "rev-1", "test", "b.mid", role="chord"),
        ]
        stats = _stats(records, "abc123")
        self.assertEqual(stats["record_count"], 2)
        self.assertEqual(
            stats["split_counts"],
            {"train": 1, "validation": 0, "test": 1},
        )
        self.assertEqual(
            stats["conditioning"]["role"],
            {"bass": 1, "chord": 1},
        )
        self.assertEqual(
            stats["reproducibility"]["manifest_sha256"],
            "abc123",
        )

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
