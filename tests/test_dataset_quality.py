#!/usr/bin/env python3
"""Tests for the deterministic Mozart dataset QA report."""

from __future__ import annotations

import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from dataset_quality import build_report, duplicate_key, record_reasons


def good_record(source_id: str, split: str = "train") -> dict:
    return {
        "schema_version": 1,
        "source_id": source_id,
        "source_revision": "rev-1",
        "source_path": f"{source_id}.mid",
        "vocabulary_id": "mozart-midi-events-v1",
        "vocabulary_size": 512,
        "conditioning": {
            "style": "electronic",
            "substyle": "techno",
            "mood": "driving",
            "rhythm": "straight",
            "role": "bass",
        },
        "music": {
            "length_bars": 4,
            "note_event_count": 1,
            "controller_event_count": 0,
            "max_start_step_polyphony": 1,
            "pitch_histogram": [1 if i == 60 else 0 for i in range(128)],
            "velocity_bin_histogram": [1] + [0] * 31,
        },
        "tokens": [1, 16, 92, 185, 256, 215, 2],
        "split": split,
    }


class DatasetQualityTests(unittest.TestCase):
    def test_valid_record_is_accepted(self) -> None:
        record = good_record("song-a")
        self.assertEqual(record_reasons(record), [])

    def test_bad_record_has_stable_reasons(self) -> None:
        record = good_record("song-a")
        record["tokens"] = [0, 600, 2]
        record["music"]["length_bars"] = 20
        reasons = record_reasons(record)
        self.assertEqual(
            reasons,
            [
                "token_out_of_range",
                "invalid_bar_length",
            ],
        )

    def test_cross_split_source_group_is_reported(self) -> None:
        left = good_record("song-a", "train")
        right = good_record("song-a", "test")
        report = build_report([left, right], manifest_sha256="abc")
        self.assertEqual(report["accepted_count"], 2)
        self.assertEqual(report["rejected_count"], 0)
        self.assertEqual(
            report["rejection_reasons"]["source_group_crosses_split"],
            1,
        )

    def test_duplicate_candidates_are_reported(self) -> None:
        left = good_record("song-a")
        right = good_record("song-b")
        report = build_report([left, right])
        self.assertEqual(len(report["duplicate_content_candidates"]), 1)
        self.assertEqual(
            report["duplicate_content_candidates"][0]["record_indexes"],
            [0, 1],
        )
        self.assertEqual(
            duplicate_key(left),
            duplicate_key(right),
        )


if __name__ == "__main__":
    unittest.main()
