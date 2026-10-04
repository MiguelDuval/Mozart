#!/usr/bin/env python3
"""Build the joint target-diverse + conditioning-diverse factorial arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from build_conditioning_context_control import (
    BASE_CONTEXT,
    CONDITIONING_CONTEXT_PROFILES,
    CONDITIONING_FIELDS,
    CONTROL_ORDER,
)

VARIANT_SUFFIX = "-context-v1"
PROFILE_PATH_RE = re.compile(r"control-probe-(?P<index>\d+)-v(?P<variant>[01])\.mid$")


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


def _target_signature(records: list[dict[str, Any]]) -> str:
    payload = [
        {
            "source_path": record["source_path"],
            "target_sha256": record["target_sha256"],
            "tokens": record["tokens"],
            "performance_controls": record["performance_controls"],
        }
        for record in records
    ]
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _conditioning_signature(record: dict[str, Any]) -> str:
    return json.dumps(
        {field: record["conditioning"][field] for field in CONDITIONING_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _require_record_shape(record: dict[str, Any], index: int) -> None:
    if not isinstance(record.get("source_id"), str) or not record["source_id"]:
        raise ValueError(f"diverse[{index}] source_id must be a non-empty string")
    if not isinstance(record.get("source_path"), str) or not record["source_path"]:
        raise ValueError(f"diverse[{index}] source_path must be a non-empty string")
    if not isinstance(record.get("tokens"), list) or len(record["tokens"]) < 2:
        raise ValueError(f"diverse[{index}] tokens must contain at least 2 ids")
    if not isinstance(record.get("target_sha256"), str) or len(record["target_sha256"]) != 64:
        raise ValueError(
            f"diverse[{index}] target_sha256 must be a SHA-256 hex string"
        )
    controls = record.get("performance_controls")
    if not isinstance(controls, dict) or set(controls) != set(CONTROL_ORDER):
        raise ValueError(f"diverse[{index}] performance_controls are malformed")
    conditioning = record.get("conditioning")
    if not isinstance(conditioning, dict):
        raise ValueError(f"diverse[{index}] conditioning must be an object")
    if any(conditioning.get(field) != BASE_CONTEXT[field] for field in CONDITIONING_FIELDS):
        raise ValueError(
            f"diverse[{index}] must start with canonical conditioning before joint intervention"
        )


def _profile_index(record: dict[str, Any]) -> int:
    match = PROFILE_PATH_RE.search(record["source_path"])
    if match is None:
        raise ValueError(
            f"cannot recover deterministic conditioning profile from source_path "
            f"{record['source_path']!r}"
        )
    index = int(match.group("index"))
    variant = int(match.group("variant"))
    if variant != 1:
        raise ValueError(
            f"joint arm expects variant-v1 source paths for conditioning intervention, "
            f"got {record['source_path']!r}"
        )
    if index < 0 or index >= len(CONDITIONING_CONTEXT_PROFILES):
        raise ValueError(f"conditioning profile index {index} is out of range")
    return index


def build_joint_context_diverse(
    diverse_train_jsonl: Path,
    output_dir: Path,
    *,
    probe_json: Path | None = None,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            f"output directory must be empty when it exists: {output_dir}"
        )

    input_records = load_jsonl(diverse_train_jsonl)
    if len(input_records) != 20:
        raise ValueError(
            f"expected exactly 20 target-diverse train records, got {len(input_records)}"
        )

    source_ids = [record["source_id"] for record in input_records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("diverse source_id values must be unique")

    for index, record in enumerate(input_records):
        _require_record_shape(record, index)

    base_records = [
        record for record in input_records
        if not record["source_id"].endswith(VARIANT_SUFFIX)
    ]
    variant_records = [
        record for record in input_records
        if record["source_id"].endswith(VARIANT_SUFFIX)
    ]
    if len(base_records) != 10 or len(variant_records) != 10:
        raise ValueError(
            "joint arm requires exactly 10 canonical base records and 10 context-v1 records"
        )

    base_by_id = {record["source_id"]: record for record in base_records}
    variant_by_parent: dict[str, dict[str, Any]] = {}
    for record in variant_records:
        parent_id = record["source_id"][: -len(VARIANT_SUFFIX)]
        if parent_id in variant_by_parent:
            raise ValueError(f"duplicate context variant for base source_id {parent_id!r}")
        variant_by_parent[parent_id] = record

    if set(base_by_id) != set(variant_by_parent):
        missing_variants = sorted(set(base_by_id) - set(variant_by_parent))
        orphan_variants = sorted(set(variant_by_parent) - set(base_by_id))
        raise ValueError(
            f"base/variant source pairing mismatch: missing={missing_variants!r} "
            f"orphan={orphan_variants!r}"
        )

    profile_by_parent: dict[str, int] = {}
    for variant in variant_records:
        profile_by_parent[
            variant["source_id"][: -len(VARIANT_SUFFIX)]
        ] = _profile_index(variant)
    if set(profile_by_parent.values()) != set(range(10)):
        raise ValueError(
            "joint arm must contain exactly conditioning profiles 0..9"
        )

    output_records: list[dict[str, Any]] = []
    changed_variant_count = 0
    target_signature_before = _target_signature(input_records)

    for source in input_records:
        output = dict(source)
        if source["source_id"].endswith(VARIANT_SUFFIX):
            parent_id = source["source_id"][: -len(VARIANT_SUFFIX)]
            profile_index = profile_by_parent[parent_id]
            conditioning = dict(source["conditioning"])
            original_seed = conditioning.get("seed")
            conditioning.update(CONDITIONING_CONTEXT_PROFILES[profile_index])
            if conditioning.get("seed") != original_seed:
                raise RuntimeError(
                    f"conditioning seed changed at variant {source['source_id']!r}"
                )
            if {
                field: conditioning[field] for field in CONDITIONING_FIELDS
            } == BASE_CONTEXT:
                raise RuntimeError(
                    f"conditioning context did not change at variant {source['source_id']!r}"
                )
            output["conditioning"] = conditioning
            changed_variant_count += 1

        for field in ("tokens", "target_sha256", "source_path", "performance_controls"):
            if output[field] != source[field]:
                raise RuntimeError(
                    f"{field} changed while building joint arm at {source['source_id']!r}"
                )
        if output["conditioning"].get("seed") != source["conditioning"].get("seed"):
            raise RuntimeError(
                f"conditioning seed changed at {source['source_id']!r}"
            )

        output_records.append(output)

    target_signature_after = _target_signature(output_records)
    if target_signature_before != target_signature_after:
        raise RuntimeError("joint intervention changed target exposure")

    conditioning_signatures = {
        _conditioning_signature(record) for record in output_records
    }
    expected_base_signature = json.dumps(
        BASE_CONTEXT,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(conditioning_signatures) != 11 or expected_base_signature not in conditioning_signatures:
        raise RuntimeError(
            "joint arm must contain canonical conditioning plus all ten diverse profiles"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "records.jsonl"
    records_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in output_records),
        encoding="utf-8",
    )

    if probe_json is not None:
        probes = json.loads(probe_json.read_text(encoding="utf-8"))
        if not isinstance(probes, dict) or not isinstance(probes.get("controls"), dict):
            raise ValueError("probe file must contain a controls object")
        (output_dir / "sequence-probes.json").write_text(
            json.dumps(probes, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    metadata = {
        "schema_version": 1,
        "status": "synthetic-joint-target-conditioning-diversity",
        "fixture_revision": "mozart-conditioning-fixture-v2",
        "production_use": False,
        "external_data": False,
        "input_train_records": len(input_records),
        "output_train_records": len(output_records),
        "target_diverse_input": True,
        "conditioning_diverse_output": True,
        "base_positions": len(base_records),
        "conditioned_variant_positions": changed_variant_count,
        "conditioning_fields": list(CONDITIONING_FIELDS),
        "canonical_conditioning": BASE_CONTEXT,
        "profiles": [
            {
                "index": index,
                "variant": 1,
                "conditioning": profile,
            }
            for index, profile in enumerate(CONDITIONING_CONTEXT_PROFILES)
        ],
        "target_signature_before_sha256": target_signature_before,
        "target_signature_after_sha256": target_signature_after,
        "target_signature_fixed": True,
        "records_path": "records.jsonl",
        "probe_path": "sequence-probes.json" if probe_json is not None else None,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "schema_version": 1,
        "status": "PASS",
        "input_train_records": len(input_records),
        "output_train_records": len(output_records),
        "base_positions": len(base_records),
        "conditioned_variant_positions": changed_variant_count,
        "conditioning_fields": list(CONDITIONING_FIELDS),
        "target_signature_fixed": True,
        "target_signature_sha256": target_signature_after,
        "distinct_conditioning_contexts": len(conditioning_signatures),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diverse_train_jsonl", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--probe-json", type=Path)
    args = parser.parse_args()

    try:
        result = build_joint_context_diverse(
            args.diverse_train_jsonl,
            args.output_dir,
            probe_json=args.probe_json,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
