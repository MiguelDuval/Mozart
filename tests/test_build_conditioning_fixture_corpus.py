#!/usr/bin/env python3
"""Tests for the control-driven synthetic development corpus."""

from __future__ import annotations

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
            self.assertEqual(values, {0.1, 0.9})

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

        self.assertEqual(result["record_count"], 12)
        self.assertEqual(len(records), 12)
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
        for profile in metadata["profiles"]:
            self.assertTrue(
                all(
                    key in profile["performance_controls"]
                    for key in CONTROL_ORDER
                )
            )


if __name__ == "__main__":
    unittest.main()
