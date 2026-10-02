#!/usr/bin/env python3
"""Validate the training-side contract of the Mozart context-diversity A/B experiment."""

from __future__ import annotations

import argparse
import json
import hashlib
import re
from pathlib import Path
from typing import Any

from build_conditioning_fixture_corpus import CONTROL_ORDER

_SOURCE_PATTERN = re.compile(r"^midi/control-probe-(\d{2})-v([01])\.mid$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _require_single_source_revision(
    records: list[dict[str, Any]],
    *,
    expected: str,
    label: str,
) -> None:
    revisions = {record.get("source_revision") for record in records}
    if revisions != {expected}:
        raise ValueError(
            f"{label} source_revision must match probe fixture revision {expected!r}"
        )


def validate_probes(
    records: list[dict[str, Any]],
    probes: dict[str, Any],
) -> dict[str, Any]:
    if probes.get("schema_version") != 1:
        raise ValueError("probe schema_version must be 1")
    if probes.get("status") != "synthetic-conditioning-sequence-probes":
        raise ValueError("unexpected probe status")
    if probes.get("probe_context") != "canonical-base-records":
        raise ValueError("probe_context must be canonical-base-records")
    if probes.get("probe_variant") != 0:
        raise ValueError("probe_variant must be 0")

    fixture_revision = probes.get("fixture_revision")
    if not isinstance(fixture_revision, str) or not fixture_revision:
        raise ValueError("probe fixture_revision must be a non-empty string")
    _require_single_source_revision(
        records,
        expected=fixture_revision,
        label="probe records",
    )

    probe_values = probes.get("control_probe_values")
    if not isinstance(probe_values, dict):
        raise ValueError("probe control_probe_values must be an object")
    expected_values = {
        "low": 0.1,
        "high": 0.9,
        "base_other_controls": 0.5,
    }
    if probe_values != expected_values:
        raise ValueError(
            f"probe control values must be {expected_values}, got {probe_values!r}"
        )

    controls = probes.get("controls")
    if not isinstance(controls, dict):
        raise ValueError("probe controls must be an object")
    if set(controls) != set(CONTROL_ORDER):
        raise ValueError(
            "probe controls must contain exactly the canonical performance controls"
        )

    by_source_id = {
        record.get("source_id"): record
        for record in records
        if isinstance(record.get("source_id"), str)
    }
    checked = 0

    for control in CONTROL_ORDER:
        entry = controls[control]
        if not isinstance(entry, dict):
            raise ValueError(f"probe {control} must be an object")

        low_id = entry.get("low_record_source_id")
        high_id = entry.get("high_record_source_id")
        low_record = by_source_id.get(low_id)
        high_record = by_source_id.get(high_id)
        if low_record is None or high_record is None:
            raise ValueError(
                f"probe {control} refers to records outside the supplied dataset"
            )

        low_profile = entry.get("low_profile")
        high_profile = entry.get("high_profile")
        if not isinstance(low_profile, dict) or not isinstance(high_profile, dict):
            raise ValueError(f"probe {control} profiles must be objects")

        expected_low = {name: 0.5 for name in CONTROL_ORDER}
        expected_high = dict(expected_low)
        expected_low[control] = 0.1
        expected_high[control] = 0.9
        if low_profile != expected_low:
            raise ValueError(f"probe {control} low_profile is inconsistent")
        if high_profile != expected_high:
            raise ValueError(f"probe {control} high_profile is inconsistent")
        if low_record.get("performance_controls") != low_profile:
            raise ValueError(f"probe {control} low record controls are inconsistent")
        if high_record.get("performance_controls") != high_profile:
            raise ValueError(f"probe {control} high record controls are inconsistent")

        _, low_variant = _identity(low_record, label=f"probe-{control}-low", index=0)
        _, high_variant = _identity(high_record, label=f"probe-{control}-high", index=0)
        if low_variant != 0 or high_variant != 0:
            raise ValueError(f"probe {control} must use canonical v0 records")
        if low_id == high_id:
            raise ValueError(f"probe {control} low/high records must differ")

        prefix = entry.get("prefix_tokens")
        prefix_length = entry.get("prefix_length")
        divergence = entry.get("first_target_divergence_index")
        if not isinstance(prefix, list) or not isinstance(prefix_length, int):
            raise ValueError(f"probe {control} prefix is malformed")
        if prefix_length != len(prefix) or prefix_length < 1:
            raise ValueError(f"probe {control} prefix_length is invalid")
        if divergence != prefix_length:
            raise ValueError(f"probe {control} divergence index is invalid")
        if prefix_length >= len(low_record["tokens"]) or prefix_length >= len(high_record["tokens"]):
            raise ValueError(f"probe {control} leaves no target token")
        if prefix != low_record["tokens"][:prefix_length]:
            raise ValueError(f"probe {control} prefix does not match low record")
        if prefix != high_record["tokens"][:prefix_length]:
            raise ValueError(f"probe {control} prefix does not match high record")
        if low_record["tokens"][prefix_length] == high_record["tokens"][prefix_length]:
            raise ValueError(f"probe {control} does not have target divergence")

        checked += 1

    return {
        "status": "PASS",
        "fixture_revision": fixture_revision,
        "probe_count": checked,
        "probe_context": probes["probe_context"],
        "probe_variant": probes["probe_variant"],
        "controls": list(CONTROL_ORDER),
    }


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

    fixture_revision = base_records[0].get("source_revision") if base_records else None
    if not isinstance(fixture_revision, str) or not fixture_revision:
        raise ValueError("base records must contain a non-empty source_revision")
    for records, label in (
        (base_records, "base"),
        (diverse_records, "diverse"),
        (matched_records, "matched"),
    ):
        _require_unique_source_ids(records, label=label)
        _require_single_source_revision(
            records,
            expected=fixture_revision,
            label=label,
        )

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
        diverse_target_sha = diverse.get("target_sha256")
        base_target_sha = base.get("target_sha256")
        matched_target_sha = matched.get("target_sha256")
        if (
            not isinstance(base_target_sha, str)
            or not base_target_sha
            or not isinstance(diverse_target_sha, str)
            or not diverse_target_sha
            or not isinstance(matched_target_sha, str)
            or not matched_target_sha
        ):
            raise ValueError(
                f"A/B train position {index} target_sha256 values must be present"
            )
        if matched_target_sha != base_target_sha:
            raise ValueError(
                f"matched[{index}] target_sha256 differs from the corresponding base target"
            )
        if diverse_variant == 1:
            matched_variant_positions += 1
            if diverse_target_sha == base_target_sha:
                raise ValueError(
                    f"diverse[{index}] variant target_sha256 unexpectedly equals base target"
                )
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
            if diverse_target_sha != base_target_sha:
                raise ValueError(
                    f"diverse[{index}] v0 target_sha256 differs from base target"
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
        "fixture_revision": fixture_revision,
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
    parser.add_argument("--probe-json", type=Path, required=True)
    parser.add_argument("--matched-probe-json", type=Path, required=True)
    args = parser.parse_args()

    base_records = load_jsonl(args.base_train_jsonl)
    diverse_records = load_jsonl(args.diverse_train_jsonl)
    matched_records = load_jsonl(args.matched_train_jsonl)
    result = validate_records(
        base_records,
        diverse_records,
        matched_records,
    )
    result["diverse_probes"] = validate_probes(
        diverse_records,
        json.loads(args.probe_json.read_text(encoding="utf-8")),
    )
    result["matched_probes"] = validate_probes(
        matched_records,
        json.loads(args.matched_probe_json.read_text(encoding="utf-8")),
    )
    result["input_fingerprint"] = {
        "base_train_sha256": sha256_file(args.base_train_jsonl),
        "diverse_train_sha256": sha256_file(args.diverse_train_jsonl),
        "matched_train_sha256": sha256_file(args.matched_train_jsonl),
        "diverse_probe_sha256": sha256_file(args.probe_json),
        "matched_probe_sha256": sha256_file(args.matched_probe_json),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
