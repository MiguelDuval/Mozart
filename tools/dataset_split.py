#!/usr/bin/env python3
"""Deterministically assign Mozart training records to source-grouped splits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


DEFAULT_BUCKETS = 10_000


def source_key(record: dict) -> str:
    source_id = str(record.get("source_id", ""))
    source_path = str(record.get("source_path", record.get("path", "")))
    source_revision = str(record.get("source_revision", ""))
    if not source_id or not source_path or not source_revision:
        raise ValueError(
            "record requires source_id, source_path (or path), and source_revision"
        )
    return f"{source_id}\0{source_path}\0{source_revision}"


def split_for_key(
    key: str,
    *,
    seed: str = "mozart-dataset-v1",
    train_per_mille: int = 900,
    validation_per_mille: int = 50,
) -> str:
    if not key:
        raise ValueError("split key must not be empty")
    if train_per_mille < 0 or validation_per_mille < 0:
        raise ValueError("split proportions must be non-negative")
    if train_per_mille + validation_per_mille > 1000:
        raise ValueError("train + validation proportions must not exceed 1000")

    digest = hashlib.sha256(f"{seed}\0{key}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % DEFAULT_BUCKETS
    train_cutoff = train_per_mille * 10
    validation_cutoff = train_cutoff + validation_per_mille * 10

    if bucket < train_cutoff:
        return "train"
    if bucket < validation_cutoff:
        return "validation"
    return "test"


def assign_records(
    records: list[dict],
    *,
    seed: str = "mozart-dataset-v1",
    train_per_mille: int = 900,
    validation_per_mille: int = 50,
) -> list[dict]:
    output: list[dict] = []
    for record in records:
        key = source_key(record)
        item = dict(record)
        item["split"] = split_for_key(
            key,
            seed=seed,
            train_per_mille=train_per_mille,
            validation_per_mille=validation_per_mille,
        )
        output.append(item)
    return output


def read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc

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


def write_jsonl(path: Path, records: list[dict]) -> None:
    payload = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    try:
        path.write_text(payload, encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot write {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    parser.add_argument("--seed", default="mozart-dataset-v1")
    parser.add_argument("--train-per-mille", type=int, default=900)
    parser.add_argument("--validation-per-mille", type=int, default=50)
    args = parser.parse_args()

    try:
        records = read_jsonl(args.input_jsonl)
        assigned = assign_records(
            records,
            seed=args.seed,
            train_per_mille=args.train_per_mille,
            validation_per_mille=args.validation_per_mille,
        )
        write_jsonl(args.output_jsonl, assigned)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    counts = {"train": 0, "validation": 0, "test": 0}
    for record in assigned:
        counts[record["split"]] += 1

    print(
        "PASS: assigned "
        f"{len(assigned)} records "
        f"(train={counts['train']} validation={counts['validation']} test={counts['test']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
