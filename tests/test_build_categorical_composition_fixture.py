#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_categorical_composition_fixture import (  # noqa: E402
    BASE_CONDITIONING,
    COMPOSITIONS,
    HIGH_VALUES,
    build_fixture,
)


class CategoricalCompositionFixtureTests(unittest.TestCase):
    def _records(self, root: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in (root / "records.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_shape_determinism_and_unseen_compositions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            expected = {"record_count": 50, "split_counts": {"train": 20, "validation": 10, "test": 20}}
            self.assertEqual(build_fixture(first), expected)
            self.assertEqual(build_fixture(second), expected)
            self.assertEqual(
                (first / "records.jsonl").read_bytes(),
                (second / "records.jsonl").read_bytes(),
            )

            records = self._records(first)
            self.assertEqual(len(records), 50)
            train = [r for r in records if r["split"] == "train"]
            self.assertEqual(
                {tuple(r["composition_axes"]) for r in train},
                {(), ("style",), ("substyle",), ("mood",), ("rhythm",), ("role",)},
            )
            self.assertTrue(all(len(r["composition_axes"]) <= 1 for r in train))

            probes = json.loads(
                (first / "composition-probes.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                list(probes["compositions"]),
                [profile for profile, _ in COMPOSITIONS],
            )
            for profile, axes in COMPOSITIONS:
                probe = probes["compositions"][profile]
                self.assertEqual(tuple(probe["axes"]), axes)
                self.assertEqual(probe["low_conditioning"], BASE_CONDITIONING)
                self.assertEqual(
                    probe["high_conditioning"],
                    {
                        **BASE_CONDITIONING,
                        **{axis: HIGH_VALUES[axis] for axis in axes},
                    },
                )
                self.assertGreater(probe["prefix_length"], 0)

    def test_test_pairs_have_shared_prefix_and_different_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixture"
            build_fixture(root)
            records = {
                r["source_id"]: r
                for r in self._records(root)
            }
            probes = json.loads(
                (root / "composition-probes.json").read_text(encoding="utf-8")
            )["compositions"]
            for probe in probes.values():
                low = records[probe["low_record_source_id"]]["tokens"]
                high = records[probe["high_record_source_id"]]["tokens"]
                prefix = probe["prefix_tokens"]
                self.assertEqual(low[:len(prefix)], prefix)
                self.assertEqual(high[:len(prefix)], prefix)
                self.assertNotEqual(low[len(prefix)], high[len(prefix)])


if __name__ == "__main__":
    unittest.main()
