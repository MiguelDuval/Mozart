#!/usr/bin/env python3
"""Tests for the Mozart context-diversity A/B training-contract validator."""

from __future__ import annotations

import sys
import unittest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tools"))

from validate_mozart_conditioning_ab import (
    compare_probe_definitions,
    sha256_file,
    validate_probes,
    validate_records,
)


def _record(
    source_id: str,
    source_path: str,
    tokens: list[int],
    density: float,
) -> dict:
    return {
        "source_id": source_id,
        "source_revision": "mozart-conditioning-fixture-v1",
        "source_path": source_path,
        "tokens": tokens,
        "target_sha256": f"sha-{source_path}",
        "performance_controls": {
            "density": density,
            "energy": 0.5,
            "syncopation": 0.5,
            "swing": 0.5,
            "variation": 0.5,
        },
    }


def _dataset() -> tuple[list[dict], list[dict], list[dict]]:
    base = [
        _record(
            f"base-{i}",
            f"midi/control-probe-{i:02d}-v0.mid",
            [10, i, 20],
            0.1 + i * 0.01,
        )
        for i in range(10)
    ]
    diverse = []
    matched = []
    for i, base_record in enumerate(base):
        for variant in (0, 1):
            path = f"midi/control-probe-{i:02d}-v{variant}.mid"
            diverse_tokens = (
                list(base_record["tokens"])
                if variant == 0
                else [10, i, 21]
            )
            diverse.append(
                _record(
                    f"diverse-{i}-{variant}",
                    path,
                    diverse_tokens,
                    base_record["performance_controls"]["density"],
                )
            )
            matched.append(
                _record(
                    f"matched-{i}-{variant}",
                    base_record["source_path"],
                    list(base_record["tokens"]),
                    base_record["performance_controls"]["density"],
                )
            )
    return base, diverse, matched


def _probe_dataset() -> tuple[list[dict], dict]:
    controls = ("density", "energy", "syncopation", "swing", "variation")
    records = []
    probe_controls = {}

    for index, control in enumerate(controls):
        low_index = index * 2
        high_index = low_index + 1
        low = {name: 0.5 for name in controls}
        high = dict(low)
        low[control] = 0.1
        high[control] = 0.9
        low_id = f"base-{low_index}"
        high_id = f"base-{high_index}"
        prefix = [100 + index]
        low_record = _record(
            low_id,
            f"midi/control-probe-{low_index:02d}-v0.mid",
            prefix + [10 + index],
            0.5,
        )
        high_record = _record(
            high_id,
            f"midi/control-probe-{high_index:02d}-v0.mid",
            prefix + [20 + index],
            0.5,
        )
        low_record["performance_controls"] = low
        high_record["performance_controls"] = high
        records.extend((low_record, high_record))
        probe_controls[control] = {
            "low_profile": low,
            "high_profile": high,
            "prefix_tokens": prefix,
            "prefix_length": 1,
            "first_target_divergence_index": 1,
            "low_record_source_id": low_id,
            "high_record_source_id": high_id,
        }

    probes = {
        "schema_version": 1,
        "fixture_revision": "mozart-conditioning-fixture-v1",
        "status": "synthetic-conditioning-sequence-probes",
        "probe_context": "canonical-base-records",
        "probe_variant": 0,
        "control_probe_values": {
            "low": 0.1,
            "high": 0.9,
            "base_other_controls": 0.5,
        },
        "max_generated_tokens": 32,
        "controls": probe_controls,
    }
    return records, probes


class MozartConditioningABValidatorTests(unittest.TestCase):
    def test_valid_canonical_probes(self) -> None:
        records, probes = _probe_dataset()
        result = validate_probes(records, probes)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["probe_count"], 5)

    def test_rejects_probe_target_divergence_mismatch(self) -> None:
        records, probes = _probe_dataset()
        probes["controls"]["density"]["first_target_divergence_index"] = 0
        with self.assertRaisesRegex(ValueError, "density divergence index is invalid"):
            validate_probes(records, probes)

    def test_rejects_variant_probe_record(self) -> None:
        records, probes = _probe_dataset()
        records[0]["source_path"] = "midi/control-probe-00-v1.mid"
        with self.assertRaisesRegex(ValueError, "must use canonical v0"):
            validate_probes(records, probes)

    def test_sha256_file_is_stable(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "input.jsonl"
            path.write_bytes(b"mozart-ab\n")
            digest = sha256_file(path)
            self.assertEqual(len(digest), 64)
            self.assertEqual(digest, sha256_file(path))

    def test_probe_definitions_accept_different_record_ids(self) -> None:
        _, probes = _probe_dataset()
        matched = __import__("copy").deepcopy(probes)
        for control, entry in matched["controls"].items():
            entry["low_record_source_id"] = f"matched-{control}-low"
            entry["high_record_source_id"] = f"matched-{control}-high"
        result = compare_probe_definitions(probes, matched)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            result["record_identity_fields_ignored"],
            ["low_record_source_id", "high_record_source_id"],
        )

    def test_rejects_probe_definition_prefix_mismatch(self) -> None:
        _, probes = _probe_dataset()
        matched = __import__("copy").deepcopy(probes)
        matched["controls"]["density"]["prefix_tokens"] = [999]
        with self.assertRaisesRegex(ValueError, "density.*prefix_tokens.*differs"):
            compare_probe_definitions(probes, matched)

    def test_rejects_probe_definition_profile_mismatch(self) -> None:
        _, probes = _probe_dataset()
        matched = __import__("copy").deepcopy(probes)
        matched["controls"]["energy"]["high_profile"]["energy"] = 0.8
        with self.assertRaisesRegex(ValueError, "energy.*high_profile.*differs"):
            compare_probe_definitions(probes, matched)

    def test_valid_matched_exposure_layout(self) -> None:
        base, diverse, matched = _dataset()
        result = validate_records(base, diverse, matched)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["diverse_variant_positions"], 10)
        self.assertEqual(result["diverse_base_positions"], 10)

    def test_rejects_source_revision_mismatch(self) -> None:
        base, diverse, matched = _dataset()
        diverse[4]["source_revision"] = "other-fixture-v9"
        with self.assertRaisesRegex(ValueError, "diverse source_revision"):
            validate_records(base, diverse, matched)

    def test_rejects_probe_revision_mismatch(self) -> None:
        records, probes = _probe_dataset()
        records[0]["source_revision"] = "other-fixture-v9"
        with self.assertRaisesRegex(ValueError, "probe records source_revision"):
            validate_probes(records, probes)

    def test_rejects_target_mismatch_in_matched_baseline(self) -> None:
        base, diverse, matched = _dataset()
        matched[7]["tokens"] = [10, 7, 99]
        with self.assertRaisesRegex(ValueError, "matched\[7\] tokens differ"):
            validate_records(base, diverse, matched)

    def test_rejects_control_mismatch(self) -> None:
        base, diverse, matched = _dataset()
        diverse[3]["performance_controls"]["density"] = 0.99
        with self.assertRaisesRegex(ValueError, "diverse\[3\] controls differ"):
            validate_records(base, diverse, matched)

    def test_rejects_missing_variant_difference(self) -> None:
        base, diverse, matched = _dataset()
        diverse[1]["tokens"] = list(base[0]["tokens"])
        diverse[1]["target_sha256"] = base[0]["target_sha256"]
        with self.assertRaisesRegex(ValueError, "variant target unexpectedly equals"):
            validate_records(base, diverse, matched)

    def test_rejects_matched_target_hash_mismatch(self) -> None:
        base, diverse, matched = _dataset()
        matched[2]["target_sha256"] = "sha-corrupt"
        with self.assertRaisesRegex(ValueError, "matched\[2\] target_sha256"):
            validate_records(base, diverse, matched)


if __name__ == "__main__":
    unittest.main()
