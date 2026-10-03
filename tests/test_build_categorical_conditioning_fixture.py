#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_categorical_conditioning_fixture import (
    CATEGORICAL_PAIRS,
    NEUTRAL_CONTROLS,
    TEST_CONTEXT,
    TRAIN_CONTEXTS,
    build_fixture,
)


class CategoricalConditioningFixtureTests(unittest.TestCase):
    def _records(self, root: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in (root / "records.jsonl").read_text().splitlines()
            if line
        ]

    def test_fixture_shape_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            self.assertEqual(
                build_fixture(first),
                {"record_count": 32, "split_counts": {"train": 20, "validation": 2, "test": 10}},
            )
            build_fixture(second)
            self.assertEqual(
                (first / "records.jsonl").read_bytes(),
                (second / "records.jsonl").read_bytes(),
            )
            records = self._records(first)
            self.assertEqual(len(records), 32)
            self.assertEqual(len({r["source_id"] for r in records}), 32)
            self.assertEqual(
                {r["split"] for r in records},
                {"train", "validation", "test"},
            )
            self.assertEqual(
                set(TRAIN_CONTEXTS),
                {r["context_seed"] for r in records if r["split"] == "train"},
            )
            self.assertEqual(
                {TEST_CONTEXT},
                {r["context_seed"] for r in records if r["split"] == "test"},
            )
            for record in records:
                self.assertEqual(record["performance_controls"], NEUTRAL_CONTROLS)

    def test_every_categorical_axis_has_held_out_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixture"
            build_fixture(root)
            records = {r["source_id"]: r for r in self._records(root)}
            probes = json.loads((root / "sequence-probes.json").read_text())
            self.assertEqual(set(probes["probes"]), set(CATEGORICAL_PAIRS))
            for axis, (low, high) in CATEGORICAL_PAIRS.items():
                probe = probes["probes"][axis]
                low_record = records[probe["low_record_source_id"]]
                high_record = records[probe["high_record_source_id"]]
                self.assertEqual(low_record["split"], "test")
                self.assertEqual(high_record["split"], "test")
                prefix = probe["prefix_tokens"]
                self.assertGreater(len(prefix), 0)
                self.assertEqual(low_record["tokens"][:len(prefix)], prefix)
                self.assertEqual(high_record["tokens"][:len(prefix)], prefix)
                self.assertNotEqual(low_record["tokens"][len(prefix)], high_record["tokens"][len(prefix)])
                for field in ("style", "substyle", "mood", "rhythm", "role"):
                    if field == axis:
                        self.assertEqual(probe["low_conditioning"][field], low)
                        self.assertEqual(probe["high_conditioning"][field], high)
                    else:
                        self.assertEqual(
                            probe["low_conditioning"][field],
                            probe["high_conditioning"][field],
                        )
                self.assertEqual(probe["performance_controls"], NEUTRAL_CONTROLS)


if __name__ == "__main__":
    unittest.main()
