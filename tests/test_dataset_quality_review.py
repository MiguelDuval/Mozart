#!/usr/bin/env python3
"""Tests for the explicit duplicate-content review gate."""

from __future__ import annotations

import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from dataset_quality import build_report, duplicate_key, _load_duplicate_reviews


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


class DuplicateReviewTests(unittest.TestCase):
    def test_intentional_duplicate_is_resolved(self) -> None:
        left = good_record("song-a")
        right = good_record("song-b")
        digest = duplicate_key(left)

        report = build_report(
            [left, right],
            duplicate_reviews={digest: {"decision": "intentional"}},
        )

        self.assertEqual(report["duplicate_content_review"]["candidate_count"], 1)
        self.assertEqual(report["duplicate_content_review"]["intentional_count"], 1)
        self.assertEqual(report["duplicate_content_review"]["unreviewed_count"], 0)
        self.assertEqual(report["duplicate_content_review"]["excluded_count"], 0)
        self.assertNotIn(
            "duplicate_content_unreviewed",
            report["rejection_reasons"],
        )

    def test_unreviewed_duplicate_is_visible(self) -> None:
        report = build_report(
            [good_record("song-a"), good_record("song-b")]
        )
        self.assertEqual(report["duplicate_content_review"]["unreviewed_count"], 1)
        self.assertEqual(
            report["rejection_reasons"]["duplicate_content_unreviewed"],
            1,
        )

    def test_exclude_decision_blocks_strict_quality_semantics(self) -> None:
        left = good_record("song-a")
        right = good_record("song-b")
        digest = duplicate_key(left)

        report = build_report(
            [left, right],
            duplicate_reviews={digest: {"decision": "exclude"}},
        )

        self.assertEqual(report["duplicate_content_review"]["excluded_count"], 1)
        self.assertEqual(
            report["rejection_reasons"]["duplicate_content_exclude_decision"],
            1,
        )

    def test_unknown_review_digest_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_report(
                [good_record("song-a"), good_record("song-b")],
                duplicate_reviews={
                    "0" * 64: {"decision": "intentional"},
                },
            )

    def test_review_file_schema_is_validated(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "reviews": {
                        "a" * 64: {"decision": "intentional"},
                    },
                }),
                encoding="utf-8",
            )
            self.assertEqual(
                _load_duplicate_reviews(path),
                {"a" * 64: {"decision": "intentional"}},
            )


if __name__ == "__main__":
    unittest.main()
