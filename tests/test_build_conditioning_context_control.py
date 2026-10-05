#!/usr/bin/env python3
"""Tests for the target-fixed conditioning-context control arm."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_conditioning_context_control import (
    BASE_CONTEXT,
    CONDITIONING_CONTEXT_PROFILES,
    build_conditioning_context_control,
)


class ConditioningContextControlTests(unittest.TestCase):
    def _base_record(self, index: int) -> dict:
        return {
            "source_id": f"base-{index}",
            "source_revision": "mozart-conditioning-fixture-v2",
            "source_path": f"midi/control-probe-{index:02d}-v0.mid",
            "tokens": [10, index, 20, 30],
            "target_sha256": f"{index:064x}"[-64:],
            "performance_controls": {
                "density": 0.5,
                "energy": 0.5,
                "syncopation": 0.5,
                "swing": 0.5,
                "variation": 0.5,
            },
            "conditioning": dict(BASE_CONTEXT),
        }

    def _fixture(self, root: Path) -> tuple[Path, Path]:
        train = root / "train.jsonl"
        records = [self._base_record(index) for index in range(10)]
        train.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )

        probes = {
            "schema_version": 1,
            "fixture_revision": "mozart-conditioning-fixture-v2",
            "status": "synthetic-conditioning-sequence-probes",
            "probe_context": "canonical-base-records",
            "probe_variant": 0,
            "control_probe_values": {
                "low": 0.1,
                "high": 0.9,
                "base_other_controls": 0.5,
            },
            "max_generated_tokens": 32,
            "controls": {},
        }
        for index, control in enumerate(
            ("density", "energy", "syncopation", "swing", "variation")
        ):
            low = index * 2
            high = low + 1
            probes["controls"][control] = {
                "low_record_source_id": f"base-{low}",
                "high_record_source_id": f"base-{high}",
                "low_profile": {
                    "density": 0.5,
                    "energy": 0.5,
                    "syncopation": 0.5,
                    "swing": 0.5,
                    "variation": 0.5,
                },
                "high_profile": {
                    "density": 0.5,
                    "energy": 0.5,
                    "syncopation": 0.5,
                    "swing": 0.5,
                    "variation": 0.5,
                },
                "prefix_tokens": [10],
                "prefix_length": 1,
                "first_target_divergence_index": 1,
            }
        path = root / "probes.json"
        path.write_text(
            json.dumps(probes, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return train, path

    def test_build_is_target_fixed_and_conditioning_diverse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train, probes = self._fixture(root)
            output = root / "out"
            result = build_conditioning_context_control(
                train,
                output,
                probe_json=probes,
            )
            records = [
                json.loads(line)
                for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            mapped_probes = json.loads(
                (output / "sequence-probes.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["record_count"], 20)
        self.assertEqual(result["variant_positions"], 10)
        self.assertEqual(len(records), 20)
        self.assertEqual(metadata["target_fixed"], True)
        self.assertEqual(metadata["performance_controls_fixed"], True)
        self.assertEqual(metadata["conditioning_seed_fixed"], True)
        self.assertEqual(
            len({tuple(profile["conditioning"].values()) for profile in metadata["profiles"]}),
            10,
        )

        for index, base in enumerate(records[::2]):
            variant = records[index * 2 + 1]
            self.assertEqual(base["tokens"], variant["tokens"])
            self.assertEqual(base["target_sha256"], variant["target_sha256"])
            self.assertEqual(
                base["performance_controls"],
                variant["performance_controls"],
            )
            self.assertEqual(base["conditioning"]["style"], BASE_CONTEXT["style"])
            self.assertEqual(
                variant["conditioning"],
                {
                    **BASE_CONTEXT,
                    **CONDITIONING_CONTEXT_PROFILES[index],
                },
            )
            self.assertNotEqual(
                base["conditioning"],
                variant["conditioning"],
            )

        for entry in mapped_probes["controls"].values():
            self.assertTrue(entry["low_record_source_id"].endswith("-ctxbase-v0"))
            self.assertTrue(entry["high_record_source_id"].endswith("-ctxbase-v0"))

    def test_rejects_noncanonical_base_conditioning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train, _ = self._fixture(root)
            records = [
                json.loads(line)
                for line in train.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            records[0]["conditioning"]["mood"] = "dark"
            train.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "canonical fixture conditioning"):
                build_conditioning_context_control(train, root / "out")


if __name__ == "__main__":
    unittest.main()
