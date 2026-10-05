#!/usr/bin/env python3
"""Build a target-fixed training arm with diverse model-visible conditioning metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_conditioning_fixture_corpus import CONTROL_ORDER, FIXTURE_REVISION


CONDITIONING_FIELDS = ("style", "substyle", "mood", "rhythm", "role")

CONDITIONING_CONTEXT_PROFILES: tuple[dict[str, str], ...] = (
    {
        "style": "electronic",
        "substyle": "dark_techno",
        "mood": "dark",
        "rhythm": "straight",
        "role": "bass",
    },
    {
        "style": "techno",
        "substyle": "techno",
        "mood": "driving",
        "rhythm": "syncopated",
        "role": "percussion",
    },
    {
        "style": "hard_techno",
        "substyle": "hard_techno",
        "mood": "aggressive",
        "rhythm": "straight",
        "role": "lead",
    },
    {
        "style": "dark_techno",
        "substyle": "dark_techno",
        "mood": "hypnotic",
        "rhythm": "swing",
        "role": "arpeggio",
    },
    {
        "style": "trap",
        "substyle": "trap",
        "mood": "tense",
        "rhythm": "half_time",
        "role": "drums",
    },
    {
        "style": "electronic",
        "substyle": "generic",
        "mood": "atmospheric",
        "rhythm": "broken",
        "role": "texture",
    },
    {
        "style": "techno",
        "substyle": "hard_techno",
        "mood": "dark",
        "rhythm": "double_time",
        "role": "percussion",
    },
    {
        "style": "dark_techno",
        "substyle": "dark_techno",
        "mood": "aggressive",
        "rhythm": "syncopated",
        "role": "chords",
    },
    {
        "style": "hard_techno",
        "substyle": "techno",
        "mood": "hypnotic",
        "rhythm": "swing",
        "role": "lead",
    },
    {
        "style": "trap",
        "substyle": "dark_trap",
        "mood": "dark",
        "rhythm": "broken",
        "role": "bass",
    },
)

BASE_CONTEXT = {
    "style": "electronic",
    "substyle": "techno",
    "mood": "driving",
    "rhythm": "straight",
    "role": "bass",
}


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


def _require_record_shape(record: dict[str, Any], index: int) -> None:
    if not isinstance(record.get("source_id"), str) or not record["source_id"]:
        raise ValueError(f"base[{index}] source_id must be a non-empty string")
    if not isinstance(record.get("tokens"), list) or len(record["tokens"]) < 2:
        raise ValueError(f"base[{index}] tokens must contain at least 2 ids")
    if not isinstance(record.get("target_sha256"), str) or len(record["target_sha256"]) != 64:
        raise ValueError(f"base[{index}] target_sha256 must be a SHA-256 hex string")
    controls = record.get("performance_controls")
    if not isinstance(controls, dict) or set(controls) != set(CONTROL_ORDER):
        raise ValueError(f"base[{index}] performance_controls are malformed")
    conditioning = record.get("conditioning")
    if not isinstance(conditioning, dict):
        raise ValueError(f"base[{index}] conditioning must be an object")
    if any(conditioning.get(name) != BASE_CONTEXT[name] for name in CONDITIONING_FIELDS):
        raise ValueError(
            f"base[{index}] must use the canonical fixture conditioning context"
        )


def build_conditioning_context_control(
    base_train_jsonl: Path,
    output_dir: Path,
    *,
    probe_json: Path | None = None,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            f"output directory must be empty when it exists: {output_dir}"
        )

    base_records = load_jsonl(base_train_jsonl)
    if len(base_records) != 10:
        raise ValueError(f"expected exactly 10 base train records, got {len(base_records)}")
    if len(CONDITIONING_CONTEXT_PROFILES) != len(base_records):
        raise RuntimeError("conditioning profile count must match base train count")

    source_ids = [record.get("source_id") for record in base_records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("base train source_id values must be unique")

    for index, record in enumerate(base_records):
        _require_record_shape(record, index)

    records: list[dict[str, Any]] = []
    source_id_map: dict[str, dict[str, str]] = {}

    for index, base in enumerate(base_records):
        original = dict(base)
        original["source_id"] = f"{base['source_id']}-ctxbase-v0"
        variant = dict(base)
        variant["source_id"] = f"{base['source_id']}-ctxdiv-v1"
        variant_conditioning = dict(base["conditioning"])
        variant_conditioning.update(CONDITIONING_CONTEXT_PROFILES[index])
        variant["conditioning"] = variant_conditioning

        if variant["tokens"] != original["tokens"]:
            raise RuntimeError(f"target tokens changed while creating position {index}")
        if variant["target_sha256"] != original["target_sha256"]:
            raise RuntimeError(f"target hash changed while creating position {index}")
        if variant["performance_controls"] != original["performance_controls"]:
            raise RuntimeError(f"performance controls changed while creating position {index}")
        if variant["conditioning"] == original["conditioning"]:
            raise RuntimeError(f"conditioning context did not change at position {index}")

        records.extend((original, variant))
        source_id_map[base["source_id"]] = {
            "variant_0": original["source_id"],
            "variant_1": variant["source_id"],
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "records.jsonl"
    records_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

    if probe_json is not None:
        probes = json.loads(probe_json.read_text(encoding="utf-8"))
        controls = probes.get("controls")
        if not isinstance(controls, dict):
            raise ValueError("probe file must contain a controls object")
        for entry in controls.values():
            for field in ("low_record_source_id", "high_record_source_id"):
                original_id = entry[field]
                mapping = source_id_map.get(original_id)
                if mapping is None:
                    raise ValueError(
                        f"probe source id {original_id!r} is not one of the base train records"
                    )
                entry[field] = mapping["variant_0"]
        (output_dir / "sequence-probes.json").write_text(
            json.dumps(probes, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    metadata = {
        "schema_version": 1,
        "status": "synthetic-conditioning-context-control",
        "fixture_revision": FIXTURE_REVISION,
        "production_use": False,
        "external_data": False,
        "base_train_records": len(base_records),
        "train_records": len(records),
        "variant_positions": len(base_records),
        "conditioning_fields": list(CONDITIONING_FIELDS),
        "target_fixed": True,
        "performance_controls_fixed": True,
        "conditioning_seed_fixed": True,
        "base_context": BASE_CONTEXT,
        "profiles": [
            {
                "index": index,
                "variant": 1,
                "conditioning": profile,
            }
            for index, profile in enumerate(CONDITIONING_CONTEXT_PROFILES)
        ],
        "records_path": "records.jsonl",
        "probe_path": "sequence-probes.json" if probe_json is not None else None,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "source-id-map.json").write_text(
        json.dumps(source_id_map, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "PASS",
        "record_count": len(records),
        "variant_positions": len(base_records),
        "output_dir": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_train_jsonl", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--probe-json", type=Path)
    args = parser.parse_args()

    try:
        result = build_conditioning_context_control(
            args.base_train_jsonl,
            args.output_dir,
            probe_json=args.probe_json,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1

    print(
        "PASS: conditioning-context control arm "
        f"records={result['record_count']} variants={result['variant_positions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
