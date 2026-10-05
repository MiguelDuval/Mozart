#!/usr/bin/env python3
"""Tests for the deterministic synthetic Mozart fixture corpus."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_fixture_corpus import FIXTURE_REVISION, build_fixture_corpus


def read_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class FixtureCorpusTests(unittest.TestCase):
    def test_fixture_corpus_is_end_to_end_and_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixture"
            result = build_fixture_corpus(root)

            self.assertEqual(result["record_count"], 5)
            self.assertEqual(result["shard_count"], 4)
            self.assertEqual(
                result["split_counts"],
                {"train": 3, "validation": 1, "test": 1},
            )
            self.assertEqual(result["qa"]["rejected_count"], 0)
            self.assertEqual(result["qa"]["source_groups_crossing_splits"], [])
            self.assertEqual(result["qa"]["duplicate_content_candidates"], [])

            stats = json.loads(
                (root / "shards" / "dataset-statistics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stats["record_count"], 5)
            self.assertEqual(stats["split_counts"], result["split_counts"])
            self.assertEqual(stats["conditioning_vocabulary_id"], "mozart-conditioning-v1")

            records = [
                json.loads(line)
                for line in (root / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(records), 5)
            self.assertTrue(all(record["source_revision"] == FIXTURE_REVISION for record in records))
            self.assertEqual(
                {
                    tuple(
                        record["performance_controls"][name]
                        for name in (
                            "density",
                            "energy",
                            "syncopation",
                            "swing",
                            "variation",
                        )
                    )
                    for record in records
                },
                {
                    (0.25, 0.7, 0.1, 0.0, 0.2),
                    (0.2, 0.6, 0.25, 0.15, 0.5),
                    (0.3, 0.55, 0.6, 0.25, 0.8),
                },
            )
            self.assertTrue(
                all(
                    4 <= record["music"]["length_bars"] <= 16
                    for record in records
                )
            )
            self.assertTrue(
                any(
                    record["music"]["time_signatures"]
                    and record["music"]["time_signatures"][0]["numerator"] == 3
                    for record in records
                )
            )
            self.assertTrue(
                any(
                    record.get("window", {}).get("start_bar") == 16
                    and record.get("window", {}).get("end_bar") == 20
                    for record in records
                )
            )

            metadata = json.loads(
                (root / "fixture-metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["status"], "synthetic-fixture")
            self.assertFalse(metadata["production_use"])
            self.assertFalse(metadata["external_data"])
            self.assertEqual(metadata["fixture_revision"], FIXTURE_REVISION)

    def test_fixture_corpus_output_is_byte_for_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left"
            right = Path(directory) / "right"
            build_fixture_corpus(left)
            build_fixture_corpus(right)
            self.assertEqual(read_tree(left), read_tree(right))


if __name__ == "__main__":
    unittest.main()
