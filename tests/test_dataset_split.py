#!/usr/bin/env python3
"""Tests for source-grouped deterministic dataset splitting."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from dataset_split import assign_records, split_for_key, source_key


class DatasetSplitTests(unittest.TestCase):
    def test_same_source_revision_always_uses_same_split(self) -> None:
        records = [
            {
                "source_id": "song-a",
                "source_path": "song-a/part1.mid",
                "source_revision": "abc",
            },
            {
                "source_id": "song-a",
                "source_path": "song-a/part2.mid",
                "source_revision": "abc",
            },
        ]
        assigned = assign_records(records)
        self.assertEqual(assigned[0]["split"], assigned[1]["split"])

    def test_revision_change_can_change_source_group_key(self) -> None:
        first = source_key(
            {
                "source_id": "song-a",
                "source_path": "song-a.mid",
                "source_revision": "abc",
            }
        )
        second = source_key(
            {
                "source_id": "song-a",
                "source_path": "song-a.mid",
                "source_revision": "def",
            }
        )
        self.assertNotEqual(first, second)

    def test_assignment_is_deterministic(self) -> None:
        records = [
            {
                "source_id": f"song-{index}",
                "source_path": f"songs/{index}.mid",
                "source_revision": "abc",
            }
            for index in range(100)
        ]
        self.assertEqual(assign_records(records), assign_records(records))

    def test_boundaries_are_source_of_truth(self) -> None:
        train_key = next(
            f"train-{index}"
            for index in range(100_000)
            if split_for_key(
                f"train-{index}",
                train_per_mille=1000,
                validation_per_mille=0,
            )
            == "train"
        )
        self.assertEqual(
            split_for_key(train_key, train_per_mille=1000, validation_per_mille=0),
            "train",
        )

    def test_invalid_proportions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            split_for_key("x", train_per_mille=800, validation_per_mille=300)


if __name__ == "__main__":
    unittest.main()
