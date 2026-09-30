#!/usr/bin/env python3
"""End-to-end test for the offline Mozart corpus packaging path."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_training_shards import write_shards
from dataset_quality import build_report
from dataset_split import assign_records, split_for_key
from midi_to_training_example import build_example


def vlq(value: int) -> bytes:
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.reverse()
    return bytes(parts)


def smf_fixture() -> bytes:
    events = bytearray()
    for _ in range(4):
        events += bytes.fromhex("00 90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
        events += vlq(240) + bytes.fromhex("90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
        events += vlq(240) + bytes.fromhex("90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
        events += vlq(240) + bytes.fromhex("90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
    events += bytes.fromhex("00 FF 2F 00")

    header = b"MThd" + bytes.fromhex("00 00 00 06 00 00 00 01 01 E0")
    track = b"MTrk" + len(events).to_bytes(4, "big") + bytes(events)
    return header + track


def source_ids_for_all_splits() -> list[str]:
    found: dict[str, str] = {}
    for index in range(10_000):
        source_id = f"fixture-source-{index}"
        split = split_for_key(f"{source_id}\0rev-1")
        found.setdefault(split, source_id)
        if len(found) == 3:
            return [found["train"], found["validation"], found["test"]]
    raise AssertionError("fixture could not find all three deterministic splits")


class CorpusPipelineIntegrationTests(unittest.TestCase):
    def test_smf_to_split_to_shards_to_quality_report(self) -> None:
        source_ids = source_ids_for_all_splits()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            midi_path = root / "fixture.mid"
            midi_path.write_bytes(smf_fixture())

            records = [
                build_example(
                    midi_path,
                    source_id=source_id,
                    source_revision="rev-1",
                    source_path=f"sources/{source_id}.mid",
                    style="electronic",
                    substyle="techno",
                    mood="driving",
                    rhythm="straight",
                    role="bass",
                    seed=12345,
                    performance_controls={
                        "density": 0.25,
                        "energy": 0.5,
                        "syncopation": 0.0,
                        "swing": 0.0,
                        "variation": 0.0,
                    },
                )
                for source_id in source_ids
            ]

            assigned = assign_records(records)
            self.assertEqual(
                {record["split"] for record in assigned},
                {"train", "validation", "test"},
            )

            input_jsonl = root / "assigned.jsonl"
            input_jsonl.write_text(
                "".join(
                    json.dumps(record, sort_keys=True) + "\n"
                    for record in assigned
                ),
                encoding="utf-8",
            )
            shard_dir = root / "shards"
            shard_paths = write_shards(assigned, shard_dir, max_records_per_shard=1)
            self.assertEqual(len(shard_paths), 3)

            report = build_report(assigned, manifest_sha256="fixture-manifest")
            self.assertEqual(report["record_count"], 3)
            self.assertEqual(report["accepted_count"], 3)
            self.assertEqual(report["rejected_count"], 0)
            self.assertEqual(
                report["split_counts"],
                {"train": 1, "validation": 1, "test": 1},
            )

            reversed_dir = root / "shards-reversed"
            write_shards(list(reversed(assigned)), reversed_dir, max_records_per_shard=1)
            self.assertEqual(
                sorted(path.read_text(encoding="utf-8") for path in shard_dir.glob("*.jsonl")),
                sorted(path.read_text(encoding="utf-8") for path in reversed_dir.glob("*.jsonl")),
            )


if __name__ == "__main__":
    unittest.main()
