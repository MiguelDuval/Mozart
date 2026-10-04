#!/usr/bin/env python3
"""Build a target-diverse training arm with canonical model-visible conditioning."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_conditioning_context_control import BASE_CONTEXT, CONDITIONING_FIELDS, CONTROL_ORDER


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        records.append(value)
    return records


def _require_record_shape(record: dict[str, Any], index: int) -> None:
    if not isinstance(record.get("source_id"), str) or not record["source_id"]:
        raise ValueError(f"diverse[{index}] source_id must be a non-empty string")
    if not isinstance(record.get("source_path"), str) or not record["source_path"]:
        raise ValueError(f"diverse[{index}] source_path must be a non-empty string")
    if not isinstance(record.get("tokens"), list) or len(record["tokens"]) < 2:
        raise ValueError(f"diverse[{index}] tokens must contain at least 2 ids")
    if not isinstance(record.get("target_sha256"), str) or len(record["target_sha256"]) != 64:
        raise ValueError(f"diverse[{index}] target_sha256 must be a SHA-256 hex string")
    controls = record.get("performance_controls")
    if not isinstance(controls, dict) or set(controls) != set(CONTROL_ORDER):
        raise ValueError(f"diverse[{index}] performance_controls are malformed")
    conditioning = record.get("conditioning")
    if not isinstance(conditioning, dict):
        raise ValueError(f"diverse[{index}] conditioning must be an object")


def _target_signature(records: list[dict[str, Any]]) -> str:
    payload = [
        {
            "source_path": record["source_path"],
            "target_sha256": record["target_sha256"],
            "tokens": record["tokens"],
        }
        for record in records
    ]
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_target_context_control(
    diverse_train_jsonl: Path,
    output_dir: Path,
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
        raise ValueError("target-diverse source_id values must be unique")

    for index, record in enumerate(input_records):
        _require_record_shape(record, index)

    input_target_signature = _target_signature(input_records)
    distinct_target_hashes = len({record["target_sha256"] for record in input_records})
    if distinct_target_hashes < 11:
        raise ValueError(
            "target-only arm requires at least 11 distinct target SHA-256 values"
        )

    output_records: list[dict[str, Any]] = []
    for index, source in enumerate(input_records):
        output = dict(source)
        output["source_id"] = f"{source['source_id']}-targetonly-canonical"
        conditioning = dict(source["conditioning"])
        original_seed = conditioning.get("seed")
        for field in CONDITIONING_FIELDS:
            conditioning[field] = BASE_CONTEXT[field]
        if original_seed is not None and conditioning.get("seed") != original_seed:
            raise RuntimeError(f"conditioning seed changed at position {index}")
        output["conditioning"] = conditioning

        for field in ("source_path", "tokens", "target_sha256", "performance_controls"):
            if output[field] != source[field]:
                raise RuntimeError(f"{field} changed at position {index}")
        for field in CONDITIONING_FIELDS:
            if output["conditioning"][field] != BASE_CONTEXT[field]:
                raise RuntimeError(
                    f"conditioning field {field!r} is not canonical at position {index}"
                )
        output_records.append(output)

    output_target_signature = _target_signature(output_records)
    if output_target_signature != input_target_signature:
        raise RuntimeError("target signature changed while building target-only arm")

    output_conditioning_signatures = {
        json.dumps(
            {field: record["conditioning"][field] for field in CONDITIONING_FIELDS},
            sort_keys=True,
            separators=(",", ":"),
        )
        for record in output_records
    }
    if output_conditioning_signatures != {
        json.dumps(BASE_CONTEXT, sort_keys=True, separators=(",", ":"))
    }:
        raise RuntimeError("target-only arm contains non-canonical conditioning")

    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "records.jsonl"
    records_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in output_records),
        encoding="utf-8",
    )

    metadata = {
        "schema_version": 1,
        "status": "synthetic-target-only-conditioning-control",
        "production_use": False,
        "external_data": False,
        "input_train_records": len(input_records),
        "output_train_records": len(output_records),
        "conditioning_fields": list(CONDITIONING_FIELDS),
        "conditioning_fixed": True,
        "canonical_conditioning": BASE_CONTEXT,
        "target_tokens_fixed_against_input": True,
        "target_hashes_fixed_against_input": True,
        "source_paths_fixed_against_input": True,
        "performance_controls_fixed_against_input": True,
        "conditioning_seed_fixed_against_input": True,
        "input_target_signature_sha256": input_target_signature,
        "output_target_signature_sha256": output_target_signature,
        "distinct_target_hashes": distinct_target_hashes,
        "records_path": "records.jsonl",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    contract = {
        "schema_version": 1,
        "status": "PASS",
        "input_train_records": len(input_records),
        "output_train_records": len(output_records),
        "conditioning_fields_fixed": list(CONDITIONING_FIELDS),
        "conditioning_fixed": True,
        "target_tokens_fixed_against_input": True,
        "target_hashes_fixed_against_input": True,
        "source_paths_fixed_against_input": True,
        "performance_controls_fixed_against_input": True,
        "conditioning_seed_fixed_against_input": True,
        "input_target_signature_sha256": input_target_signature,
        "output_target_signature_sha256": output_target_signature,
        "distinct_target_hashes": distinct_target_hashes,
    }
    return contract


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diverse_train_jsonl", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    try:
        contract = build_target_context_control(
            args.diverse_train_jsonl, args.output_dir
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1

    print(json.dumps(contract, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
