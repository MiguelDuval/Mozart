#!/usr/bin/env python3
"""Validate the training-side contract of the Mozart context-diversity A/B experiment."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_SOURCE_PATTERN = re.compile(r"^midi/control-probe-(\d{2})-v([01])\.mid$")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        records.append(value)
    return records


def _identity(record: dict[str, Any], *, label: str, index: int) -> tuple[int, int]:
    source_path = record.get("source_path")
    if not isinstance(source_path, str):
        raise ValueError(f"{label}[{index}] has no string source_path")
    match = _SOURCE_PATTERN.fullmatch(source_path)
    if match is None:
        raise ValueError(
            f"{label}[{index}] has unexpected conditioning fixture source_path: "
            f"{source_path!r}"
        )
    return int(match.group(1)), int(match.group(2))


def _require_unique_source_ids(records: list[dict[str, Any]], *, label: str) -> None:
    source_ids = [record.get("source_id") for record in records]
    if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
        raise ValueError(f"{label} contains a missing or invalid source_id")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(f"{label} source_id values must be unique")


def validate_records(
    base_records: list[dict[str, Any]],
    diverse_records: list[dict[str, Any]],
    matched_records: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_base_count = 10
    expected_diverse_count = 20

    if len(base_records) != expected_base_count:
        raise ValueError(
            f"expected {expected_base_count} base train records, got {len(base_records)}"
        )
    if len(diverse_records) != expected_diverse_count:
        raise ValueError(
            f"expected {expected_diverse_count} diverse train records, got {len(diverse_records)}"
        )
    if len(matched_records) != expected_diverse_count:
        raise ValueError(
            f"expected {expected_diverse_count} matched train records, got {len(matched_records)}"
        )

    for records, label in (
        (base_records, "base"),
        (diverse_records, "diverse"),
        (matched_records, "matched"),
    ):
        _require_unique_source_ids(records, label=label)

    base_by_profile: dict[int, dict[str, Any]] = {}
    for index, record in enumerate(base_records):
        profile_index, variant = _identity(record, label="base", index=index)
        if variant != 0:
            raise ValueError(f"base[{index}] is not a v0 record")
        if profile_index in base_by_profile:
            raise ValueError(f"duplicate base profile index {profile_index}")
        base_by_profile[profile_index] = record

    if set(base_by_profile) != set(range(expected_base_count)):
        raise ValueError(
            "base train records must contain exactly fixture profiles 0..9"
        )

    matched_variant_positions = 0
    matched_base_positions = 0
    for index, (diverse, matched) in enumerate(zip(diverse_records, matched_records)):
        diverse_profile, diverse_variant = _identity(
            diverse,
            label="diverse",
            index=index,
        )
        matched_profile, matched_variant = _identity(
            matched,
            label="matched",
            index=index,
        )

        if matched_variant != 0:
            raise ValueError(f"matched[{index}] must reference a base v0 target")
        if diverse_variant not in (0, 1):
            raise ValueError(f"diverse[{index}] has unsupported variant {diverse_variant}")
        if diverse_profile != matched_profile:
            raise ValueError(
                f"profile-order mismatch at train position {index}: "
                f"diverse profile={diverse_profile}, matched profile={matched_profile}"
            )

        base = base_by_profile.get(diverse_profile)
        if base is None:
            raise ValueError(
                f"diverse[{index}] references unknown base profile {diverse_profile}"
            )

        if diverse.get("performance_controls") != base.get("performance_controls"):
            raise ValueError(
                f"diverse[{index}] controls differ from its base profile"
            )
        if matched.get("performance_controls") != diverse.get("performance_controls"):
            raise ValueError(
                f"matched[{index}] controls differ from diverse train position"
            )

        if matched.get("source_path") != base.get("source_path"):
            raise ValueError(
                f"matched[{index}] source_path must remain the base target path"
            )
        if matched.get("tokens") != base.get("tokens"):
            raise ValueError(
                f"matched[{index}] tokens differ from the corresponding base target"
            )

        if diverse_variant == 1:
            matched_variant_positions += 1
            if diverse.get("tokens") == base.get("tokens"):
                raise ValueError(
                    f"diverse[{index}] variant target unexpectedly equals base target"
                )
        else:
            matched_base_positions += 1
            if diverse.get("tokens") != base.get("tokens"):
                raise ValueError(
                    f"diverse[{index}] v0 target differs from base target"
                )

    if matched_variant_positions != expected_base_count:
        raise ValueError(
            "diverse train ordering must contain exactly 10 context variants"
        )
    if matched_base_positions != expected_base_count:
        raise ValueError(
            "diverse train ordering must contain exactly 10 base positions"
        )

    return {
        "status": "PASS",
        "base_train_records": len(base_records),
        "diverse_train_records": len(diverse_records),
        "matched_train_records": len(matched_records),
        "diverse_variant_positions": matched_variant_positions,
        "diverse_base_positions": matched_base_positions,
        "matching": {
            "controls": True,
            "base_target_order": True,
            "matched_target_tokens": True,
            "variant_target_difference": True,
            "source_ids_unique": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-train-jsonl", type=Path, required=True)
    parser.add_argument("--diverse-train-jsonl", type=Path, required=True)
    parser.add_argument("--matched-train-jsonl", type=Path, required=True)
    args = parser.parse_args()

    result = validate_records(
        load_jsonl(args.base_train_jsonl),
        load_jsonl(args.diverse_train_jsonl),
        load_jsonl(args.matched_train_jsonl),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
