#!/usr/bin/env python3
"""Tests for the control-driven synthetic development corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_conditioning_fixture_corpus import (
    BASE_PROFILE,
    CONTROL_ORDER,
    CONTROL_PROFILES,
    build_conditioning_fixture_corpus,
)


class ConditioningFixtureTests(unittest.TestCase):
    def test_fixture_has_two_levels_for_every_control(self) -> None:
        self.assertEqual(len(CONTROL_PROFILES), 12)
        for name in CONTROL_ORDER:
            values = {
                profile[name]
                for profile in CONTROL_PROFILES
            }
            self.assertIn(0.1, values)
            self.assertIn(0.9, values)

    def test_fixture_targets_change_when_each_control_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixture"
            result = build_conditioning_fixture_corpus(root)

            records = [
                json.loads(line)
                for line in (root / "records.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            probes = json.loads(
                (root / "sequence-probes.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["record_count"], 12)
        self.assertEqual(len(records), 12)
        self.assertEqual(
            probes["status"],
            "synthetic-conditioning-sequence-probes",
        )
        self.assertEqual(probes["probe_context"], "canonical-base-records")
        self.assertEqual(probes["probe_variant"], 0)
        self.assertEqual(
            set(probes["controls"]),
            set(CONTROL_ORDER),
        )
        for control in CONTROL_ORDER:
            probe = probes["controls"][control]
            self.assertGreaterEqual(probe["prefix_length"], 1)
            low_profile = dict(BASE_PROFILE)
            low_profile[control] = 0.1
            high_profile = dict(BASE_PROFILE)
            high_profile[control] = 0.9
            self.assertEqual(probe["low_profile"], low_profile)
            self.assertEqual(probe["high_profile"], high_profile)

            low_record = next(
                record
                for record in records
                if record["performance_controls"] == low_profile
            )
            high_record = next(
                record
                for record in records
                if record["performance_controls"] == high_profile
            )
            prefix_length = probe["prefix_length"]
            self.assertEqual(
                probe["prefix_tokens"],
                low_record["tokens"][:prefix_length],
            )
            self.assertEqual(
                probe["prefix_tokens"],
                high_record["tokens"][:prefix_length],
            )
            self.assertLess(prefix_length, len(low_record["tokens"]))
            self.assertLess(prefix_length, len(high_record["tokens"]))
            self.assertNotEqual(
                low_record["tokens"][prefix_length],
                high_record["tokens"][prefix_length],
            )
            self.assertEqual(
                probe["first_target_divergence_index"],
                prefix_length,
            )
        self.assertEqual(
            {record["split"] for record in records},
            {"train", "validation", "test"},
        )
        self.assertEqual(
            {
                split: sum(record["split"] == split for record in records)
                for split in ("train", "validation", "test")
            },
            {"train": 10, "validation": 1, "test": 1},
        )
        self.assertTrue(
            all(
                record["split"] == "train"
                for record in records[:10]
            )
        )
        self.assertEqual(records[10]["split"], "validation")
        self.assertEqual(records[11]["split"], "test")

        for control in CONTROL_ORDER:
            grouped: dict[float, list[tuple[int, ...]]] = {0.1: [], 0.9: []}
            for record in records:
                controls = record["performance_controls"]
                if all(
                    controls[name]
                    == (0.1 if name == control else BASE_PROFILE[name])
                    for name in CONTROL_ORDER
                ) or all(
                    controls[name]
                    == (0.9 if name == control else BASE_PROFILE[name])
                    for name in CONTROL_ORDER
                ):
                    grouped[controls[control]].append(tuple(record["tokens"]))

            self.assertEqual(len(grouped[0.1]), 1)
            self.assertEqual(len(grouped[0.9]), 1)
            self.assertNotEqual(
                grouped[0.1][0],
                grouped[0.9][0],
                msg=f"target token stream did not react to {control}",
            )

    def test_context_variant_count_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixture"
            with self.assertRaisesRegex(
                ValueError,
                "context_variant_count must be between 0",
            ):
                build_conditioning_fixture_corpus(
                    root,
                    context_variant_count=len(CONTROL_PROFILES) + 1,
                )

    def test_context_variants_change_targets_without_changing_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixture"
            result = build_conditioning_fixture_corpus(
                root,
                context_variant_count=10,
            )
            records = [
                json.loads(line)
                for line in (root / "records.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            metadata = json.loads(
                (root / "fixture-metadata.json")
                .read_text(encoding="utf-8")
            )
            probes = json.loads(
                (root / "sequence-probes.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["record_count"], 22)
        self.assertEqual(result["context_variant_count"], 10)
        self.assertEqual(len(records), 22)
        self.assertEqual(
            len({record["source_id"] for record in records}),
            22,
        )
        self.assertEqual(metadata["context_variant_count"], 10)
        split_counts = {
            split: sum(record["split"] == split for record in records)
            for split in ("train", "validation", "test")
        }
        self.assertEqual(
            split_counts,
            {"train": 20, "validation": 1, "test": 1},
        )

        variants_by_profile: dict[tuple[float, ...], list[dict]] = {}
        for record in records:
            key = tuple(
                float(record["performance_controls"][name])
                for name in CONTROL_ORDER
            )
            variants_by_profile.setdefault(key, []).append(record)

        for profile in CONTROL_PROFILES[:10]:
            key = tuple(float(profile[name]) for name in CONTROL_ORDER)
            variants = variants_by_profile[key]
            self.assertEqual(len(variants), 2)
            self.assertNotEqual(
                variants[0]["tokens"],
                variants[1]["tokens"],
            )
            self.assertEqual(
                variants[0]["performance_controls"],
                variants[1]["performance_controls"],
            )
            self.assertEqual(
                variants[0]["split"],
                variants[1]["split"],
            )
            self.assertNotEqual(
                variants[0]["source_id"],
                variants[1]["source_id"],
            )
            self.assertTrue(
                isinstance(variants[0]["target_sha256"], str)
                and len(variants[0]["target_sha256"]) == 64
            )
            self.assertTrue(
                isinstance(variants[1]["target_sha256"], str)
                and len(variants[1]["target_sha256"]) == 64
            )
            self.assertNotEqual(
                variants[0]["target_sha256"],
                variants[1]["target_sha256"],
            )
            self.assertEqual(
                variants[0]["split"],
                "train",
            )

        train_ids = {
            record["source_id"]
            for record in records
            if record["split"] == "train"
        }
        self.assertEqual(probes["probe_context"], "canonical-base-records")
        self.assertEqual(probes["probe_variant"], 0)
        self.assertTrue(
            all(
                "-context-v" not in source_id
                for entry in probes["controls"].values()
                for source_id in (
                    entry["low_record_source_id"],
                    entry["high_record_source_id"],
                )
            )
        )
        for entry in probes["controls"].values():
            self.assertIn(entry["low_record_source_id"], train_ids)
            self.assertIn(entry["high_record_source_id"], train_ids)
        self.assertEqual(
            len(probes["controls"]),
            len(CONTROL_ORDER),
        )

    def test_context_variant_probe_file_uses_v1_training_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixture"
            build_conditioning_fixture_corpus(
                root,
                context_variant_count=10,
            )
            records = [
                json.loads(line)
                for line in (root / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            probes = json.loads(
                (root / "sequence-probes-v1.json").read_text(encoding="utf-8")
            )

        train_ids = {
            record["source_id"]
            for record in records
            if record["split"] == "train"
        }
        self.assertEqual(probes["probe_context"], "context-variant-records")
        self.assertEqual(probes["probe_variant"], 1)
        for entry in probes["controls"].values():
            low_id = entry["low_record_source_id"]
            high_id = entry["high_record_source_id"]
            self.assertIn(low_id, train_ids)
            self.assertIn(high_id, train_ids)
            self.assertIn("-context-v1", low_id)
            self.assertIn("-context-v1", high_id)

    def test_record_target_hash_matches_midi_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixture"
            build_conditioning_fixture_corpus(
                root,
                context_variant_count=10,
            )
            records = [
                json.loads(line)
                for line in (root / "records.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            for record in records:
                midi_path = root / record["source_path"]
                digest = hashlib.sha256(midi_path.read_bytes()).hexdigest()
                self.assertEqual(record["target_sha256"], digest)

    def test_fixture_is_byte_for_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left"
            right = Path(directory) / "right"
            build_conditioning_fixture_corpus(left)
            build_conditioning_fixture_corpus(right)

            def tree(root: Path) -> dict[str, bytes]:
                return {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                }

            self.assertEqual(tree(left), tree(right))

    def test_fixture_is_explicit_and_non_production(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixture"
            build_conditioning_fixture_corpus(root)

            metadata = json.loads(
                (root / "fixture-metadata.json")
                .read_text(encoding="utf-8")
            )

        self.assertEqual(
            metadata["status"],
            "synthetic-conditioning-fixture",
        )
        self.assertFalse(metadata["production_use"])
        self.assertFalse(metadata["external_data"])
        self.assertEqual(
            metadata["control_order"],
            list(CONTROL_ORDER),
        )
        self.assertEqual(metadata["context_variant_count"], 0)
        for profile in metadata["profiles"]:
            self.assertEqual(profile["variant"], 0)
            self.assertTrue(
                all(
                    key in profile["performance_controls"]
                    for key in CONTROL_ORDER
                )
            )


if __name__ == "__main__":
    unittest.main()
