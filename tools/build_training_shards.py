#!/usr/bin/env python3
"""Build deterministic Mozart JSONL training shards and corpus statistics."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_split import source_key


SPLITS = ("train", "validation", "test")
VOCABULARY_ID = "mozart-midi-events-v1"
VOCABULARY_SIZE = 512


def read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc

    records: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: record must be an object")
        records.append(value)
    return records


def _require_string(record: dict, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"record.{key} must be a non-empty string")
    return value


def validate_records(records: list[dict]) -> None:
    seen_sources: dict[str, str] = {}
    for index, record in enumerate(records):
        where = f"record[{index}]"
        if record.get("schema_version") != 1:
            raise ValueError(f"{where}.schema_version must be 1")
        if record.get("vocabulary_id") != VOCABULARY_ID:
            raise ValueError(f"{where}.vocabulary_id must be {VOCABULARY_ID}")
        if record.get("vocabulary_size") != VOCABULARY_SIZE:
            raise ValueError(f"{where}.vocabulary_size must be {VOCABULARY_SIZE}")

        _require_string(record, "source_id")
        _require_string(record, "source_revision")
        split = record.get("split")
        if split not in SPLITS:
            raise ValueError(f"{where}.split must be one of {SPLITS}")

        source = source_key(record)
        prior_split = seen_sources.get(source)
        if prior_split is not None and prior_split != split:
            raise ValueError(
                f"{where}: source group {source!r} crosses split boundaries "
                f"({prior_split} vs {split})"
            )
        seen_sources[source] = split

        tokens = record.get("tokens")
        if not isinstance(tokens, list) or not tokens:
            raise ValueError(f"{where}.tokens must be a non-empty list")
        if any(
            not isinstance(token, int) or not 0 <= token < VOCABULARY_SIZE
            for token in tokens
        ):
            raise ValueError(f"{where}.tokens contains an out-of-range token")

        music = record.get("music")
        if not isinstance(music, dict):
            raise ValueError(f"{where}.music must be an object")
        bars = music.get("length_bars")
        if not isinstance(bars, int) or not 1 <= bars <= 16:
            raise ValueError(f"{where}.music.length_bars must be 1..16")
        note_count = music.get("note_event_count")
        control_count = music.get("controller_event_count")
        max_polyphony = music.get("max_start_step_polyphony")
        if not isinstance(note_count, int) or note_count < 0 or note_count > 4096:
            raise ValueError(f"{where}.music.note_event_count must be 0..4096")
        if not isinstance(control_count, int) or control_count < 0 or control_count > 1024:
            raise ValueError(f"{where}.music.controller_event_count must be 0..1024")
        if not isinstance(max_polyphony, int) or max_polyphony < 0:
            raise ValueError(f"{where}.music.max_start_step_polyphony must be non-negative")
        pitch_histogram = music.get("pitch_histogram")
        velocity_histogram = music.get("velocity_bin_histogram")
        if not isinstance(pitch_histogram, list) or len(pitch_histogram) != 128:
            raise ValueError(f"{where}.music.pitch_histogram must contain 128 bins")
        if not isinstance(velocity_histogram, list) or len(velocity_histogram) != 32:
            raise ValueError(f"{where}.music.velocity_bin_histogram must contain 32 bins")
        if sum(pitch_histogram) != note_count:
            raise ValueError(f"{where}.music.pitch_histogram total must equal note_event_count")
        if sum(velocity_histogram) != note_count:
            raise ValueError(f"{where}.music.velocity_bin_histogram total must equal note_event_count")

        conditioning = record.get("conditioning")
        if not isinstance(conditioning, dict):
            raise ValueError(f"{where}.conditioning must be an object")
        for key in ("style", "substyle", "mood", "rhythm", "role"):
            _require_string(conditioning, key)


def _stable_record_key(record: dict) -> tuple[str, str, str, str]:
    payload = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return (
        str(record["source_id"]),
        str(record["source_revision"]),
        str(record.get("source_path", "")),
        digest,
    )


def _stats(records: list[dict], manifest_sha256: str | None) -> dict:
    split_counts = Counter(str(record["split"]) for record in records)
    style_counts = Counter(
        str(record["conditioning"]["style"]) for record in records
    )
    role_counts = Counter(
        str(record["conditioning"]["role"]) for record in records
    )
    token_lengths = [len(record["tokens"]) for record in records]
    bar_lengths = [record["music"]["length_bars"] for record in records]
    source_groups = {
        source_key(record) for record in records
    }
    note_event_count = sum(record["music"]["note_event_count"] for record in records)
    controller_event_count = sum(
        record["music"]["controller_event_count"] for record in records
    )
    max_polyphony = max(
        (record["music"]["max_start_step_polyphony"] for record in records),
        default=0,
    )
    pitch_histogram = [0] * 128
    velocity_histogram = [0] * 32
    for record in records:
        for index, value in enumerate(record["music"]["pitch_histogram"]):
            pitch_histogram[index] += value
        for index, value in enumerate(record["music"]["velocity_bin_histogram"]):
            velocity_histogram[index] += value

    return {
        "schema_version": 1,
        "vocabulary_id": VOCABULARY_ID,
        "record_count": len(records),
        "source_group_count": len(source_groups),
        "split_counts": {split: split_counts.get(split, 0) for split in SPLITS},
        "token_statistics": {
            "total": sum(token_lengths),
            "min": min(token_lengths) if token_lengths else 0,
            "max": max(token_lengths) if token_lengths else 0,
            "mean": (sum(token_lengths) / len(token_lengths))
            if token_lengths
            else 0.0,
        },
        "bar_statistics": {
            "min": min(bar_lengths) if bar_lengths else 0,
            "max": max(bar_lengths) if bar_lengths else 0,
            "mean": (sum(bar_lengths) / len(bar_lengths))
            if bar_lengths
            else 0.0,
        },
        "musical_event_statistics": {
            "note_event_count": note_event_count,
            "controller_event_count": controller_event_count,
            "max_start_step_polyphony": max_polyphony,
            "pitch_histogram": pitch_histogram,
            "velocity_bin_histogram": velocity_histogram,
        },
        "conditioning": {
            "style": dict(sorted(style_counts.items())),
            "role": dict(sorted(role_counts.items())),
        },
        "reproducibility": {
            "manifest_sha256": manifest_sha256 or "NOT_SUPPLIED",
            "split_algorithm": "sha256(seed\\0source_id\\0source_revision) mod 10000",
            "vocabulary_id": VOCABULARY_ID,
        },
    }


def write_shards(
    records: list[dict], output_dir: Path, max_records_per_shard: int
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for split in SPLITS:
        subset = [record for record in records if record["split"] == split]
        subset.sort(key=_stable_record_key)
        for shard_index, start in enumerate(
            range(0, len(subset), max_records_per_shard)
        ):
            path = output_dir / f"{split}-{shard_index:05d}.jsonl"
            payload = "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for record in subset[start : start + max_records_per_shard]
            )
            path.write_text(payload, encoding="utf-8")
            paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-records-per-shard", type=int, default=1024)
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()

    if args.max_records_per_shard <= 0:
        print("ERROR: --max-records-per-shard must be positive", file=sys.stderr)
        return 1

    try:
        records = read_jsonl(args.input_jsonl)
        validate_records(records)
        paths = write_shards(
            records, args.output_dir, args.max_records_per_shard
        )
        stats_path = args.output_dir / "dataset-statistics.json"
        stats_path.write_text(
            json.dumps(
                _stats(records, args.manifest_sha256),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: wrote {len(paths)} shards and statistics for "
        f"{len(records)} records to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
