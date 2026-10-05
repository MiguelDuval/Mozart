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
from manifest_digest import digest as manifest_digest
from verify_manifest_inventory import verify as verify_manifest_inventory
from mozart_conditioning import (
    CONDITIONING_VOCABULARY_ID,
    PERFORMANCE_CONTROL_NAMES,
    validate_conditioning,
    validate_performance_controls,
)


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
        if (
            not isinstance(pitch_histogram, list)
            or len(pitch_histogram) != 128
            or not all(isinstance(value, int) and value >= 0 for value in pitch_histogram)
        ):
            raise ValueError(f"{where}.music.pitch_histogram must contain 128 non-negative integer bins")
        if (
            not isinstance(velocity_histogram, list)
            or len(velocity_histogram) != 32
            or not all(isinstance(value, int) and value >= 0 for value in velocity_histogram)
        ):
            raise ValueError(f"{where}.music.velocity_bin_histogram must contain 32 non-negative integer bins")
        if sum(pitch_histogram) != note_count:
            raise ValueError(f"{where}.music.pitch_histogram total must equal note_event_count")
        if sum(velocity_histogram) != note_count:
            raise ValueError(f"{where}.music.velocity_bin_histogram total must equal note_event_count")

        conditioning = record.get("conditioning")
        performance_controls = record.get("performance_controls")
        if not isinstance(conditioning, dict):
            raise ValueError(f"{where}.conditioning must be an object")
        if not isinstance(performance_controls, dict):
            raise ValueError(f"{where}.performance_controls must be an object")
        if record.get("conditioning_vocabulary_id") != CONDITIONING_VOCABULARY_ID:
            raise ValueError(
                f"{where}.conditioning_vocabulary_id must be {CONDITIONING_VOCABULARY_ID}"
            )
        for key in ("style", "substyle", "mood", "rhythm", "role"):
            _require_string(conditioning, key)
        try:
            validate_conditioning(
                style=conditioning["style"],
                substyle=conditioning["substyle"],
                mood=conditioning["mood"],
                rhythm=conditioning["rhythm"],
                role=conditioning["role"],
                seed=conditioning.get("seed", 0),
            )
            validate_performance_controls(performance_controls)
        except ValueError as exc:
            raise ValueError(f"{where}.conditioning is invalid: {exc}") from exc


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


def _resolve_manifest_sha256(
    manifest_path: Path | None,
    explicit_sha256: str | None,
) -> str:
    if manifest_path is None:
        return explicit_sha256 or "NOT_SUPPLIED"

    computed = manifest_digest(manifest_path)
    if explicit_sha256 is not None and explicit_sha256.lower() != computed.lower():
        raise ValueError(
            "manifest SHA-256 does not match --manifest-sha256: "
            f"expected={computed} provided={explicit_sha256}"
        )
    return computed


def _validate_training_manifest_metadata(manifest: dict) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("training manifest schema_version must be 1")
    if manifest.get("status") not in {"audited", "release"}:
        raise ValueError(
            "training shards require an audited or release dataset manifest"
        )
    if manifest.get("license_policy") != "commercial-compatible-only":
        raise ValueError(
            "training manifest license_policy must be commercial-compatible-only"
        )
    if manifest.get("project_vocabulary_id") != VOCABULARY_ID:
        raise ValueError(
            f"training manifest project_vocabulary_id must be {VOCABULARY_ID}"
        )

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("training manifest must contain at least one source")

    seen_source_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, source in enumerate(sources):
        where = f"manifest.sources[{index}]"
        if not isinstance(source, dict):
            raise ValueError(f"{where} must be an object")
        source_id = _require_string(source, "source_id")
        revision = _require_string(source, "revision")
        if source_id in seen_source_ids:
            raise ValueError(f"duplicate manifest source_id: {source_id}")
        seen_source_ids.add(source_id)
        if revision.startswith("REPLACE"):
            raise ValueError(f"{where}.revision must be immutable")

        license_info = source.get("license")
        if not isinstance(license_info, dict):
            raise ValueError(f"{where}.license must be an object")
        if license_info.get("commercial_use") != "allowed":
            raise ValueError(
                f"{where}.license.commercial_use must be allowed"
            )
        if license_info.get("redistribution") != "allowed":
            raise ValueError(
                f"{where}.license.redistribution must be allowed"
            )
        if not isinstance(license_info.get("spdx_id"), str) or not license_info["spdx_id"].strip():
            raise ValueError(f"{where}.license.spdx_id must be concrete")

        provenance = source.get("provenance")
        if not isinstance(provenance, dict):
            raise ValueError(f"{where}.provenance must be an object")
        rights_evidence = provenance.get("rights_evidence")
        if not isinstance(rights_evidence, str) or not rights_evidence.strip() or rights_evidence.startswith("REPLACE"):
            raise ValueError(
                f"{where}.provenance.rights_evidence must be recorded"
            )

        files = source.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError(f"{where}.files must contain at least one file")
        for file_index, item in enumerate(files):
            file_where = f"{where}.files[{file_index}]"
            if not isinstance(item, dict):
                raise ValueError(f"{file_where} must be an object")
            file_path = _require_string(item, "path")
            if file_path == "REPLACE":
                raise ValueError(f"{file_where}.path must be concrete")
            checksum = item.get("sha256")
            if not isinstance(checksum, str) or len(checksum) != 64 or checksum == "REPLACE":
                raise ValueError(f"{file_where}.sha256 must be verified")
            size = item.get("size_bytes")
            if not isinstance(size, int) or size < 0:
                raise ValueError(f"{file_where}.size_bytes must be non-negative")
            if file_path in seen_paths:
                raise ValueError(f"duplicate manifest file path: {file_path}")
            seen_paths.add(file_path)


def _validate_training_record_provenance(
    records: list[dict],
    manifest: dict,
) -> None:
    source_revisions: dict[str, str] = {}
    file_owners: dict[str, tuple[str, str]] = {}

    for source in manifest["sources"]:
        source_id = str(source["source_id"])
        revision = str(source["revision"])
        source_revisions[source_id] = revision
        for item in source["files"]:
            file_owners[str(item["path"])] = (source_id, revision)

    referenced_files: set[str] = set()
    for index, record in enumerate(records):
        where = f"record[{index}]"
        source_id = _require_string(record, "source_id")
        revision = _require_string(record, "source_revision")
        source_path = _require_string(record, "source_path")

        expected_revision = source_revisions.get(source_id)
        if expected_revision is None:
            raise ValueError(
                f"{where}.source_id {source_id!r} is absent from training manifest"
            )
        if revision != expected_revision:
            raise ValueError(
                f"{where}.source_revision does not match manifest source "
                f"{source_id!r}: expected={expected_revision!r} actual={revision!r}"
            )

        owner = file_owners.get(source_path)
        if owner is None:
            raise ValueError(
                f"{where}.source_path {source_path!r} is absent from the audited "
                "manifest/inventory"
            )
        if owner != (source_id, revision):
            raise ValueError(
                f"{where}.source_path {source_path!r} belongs to "
                f"source_id={owner[0]!r} revision={owner[1]!r}, not "
                f"source_id={source_id!r} revision={revision!r}"
            )
        referenced_files.add(source_path)

    if not referenced_files:
        raise ValueError("training records must reference at least one manifest file")


def _prepare_training_provenance(
    records: list[dict],
    manifest_path: Path,
    inventory_path: Path,
    explicit_manifest_sha256: str | None,
) -> tuple[dict, str, str]:
    manifest = _read_manifest(manifest_path)
    _validate_training_manifest_metadata(manifest)

    inventory_result = verify_manifest_inventory(manifest_path, inventory_path)
    if inventory_result["manifest_id"] != manifest.get("manifest_id"):
        raise ValueError("manifest/inventory verification returned mismatched manifest_id")

    effective_manifest_sha256 = _resolve_manifest_sha256(
        manifest_path,
        explicit_manifest_sha256,
    )
    _validate_training_record_provenance(records, manifest)
    return (
        manifest,
        effective_manifest_sha256,
        str(inventory_result["inventory_digest"]),
    )


def _read_manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("dataset manifest root must be an object")
    if value.get("status") not in {"audited", "release"}:
        raise ValueError("dataset statistics require an audited or release manifest")
    sources = value.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("dataset manifest must contain at least one source")
    return value


def _manifest_source_metadata(manifest: dict) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for index, source in enumerate(manifest["sources"]):
        if not isinstance(source, dict):
            raise ValueError(f"manifest.sources[{index}] must be an object")
        source_id = source.get("source_id")
        license_info = source.get("license")
        provenance = source.get("provenance")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError(f"manifest.sources[{index}].source_id must be a non-empty string")
        if source_id in metadata:
            raise ValueError(f"duplicate manifest source_id: {source_id}")
        if not isinstance(license_info, dict) or not isinstance(provenance, dict):
            raise ValueError(f"manifest.sources[{index}] license/provenance must be objects")
        values = (
            license_info.get("spdx_id"),
            license_info.get("commercial_use"),
            license_info.get("redistribution"),
            license_info.get("attribution"),
            provenance.get("provider"),
        )
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError(f"manifest.sources[{index}] has incomplete license/provenance metadata")
        metadata[source_id] = {
            "spdx_id": values[0],
            "commercial_use": values[1],
            "redistribution": values[2],
            "attribution": values[3],
            "provider": values[4],
        }
    return metadata


def _stats(
    records: list[dict],
    manifest_sha256: str | None,
    manifest: dict | None = None,
    inventory_sha256: str | None = None,
) -> dict:
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
    source_record_counts = Counter(source_key(record) for record in records)
    performance_control_statistics = {}
    for name in PERFORMANCE_CONTROL_NAMES:
        values = [float(record["performance_controls"][name]) for record in records]
        performance_control_statistics[name] = {
            "min": min(values) if values else 0.0,
            "max": max(values) if values else 0.0,
            "mean": (sum(values) / len(values)) if values else 0.0,
            "non_zero_fraction": (
                sum(value > 0.0 for value in values) / len(values)
                if values
                else 0.0
            ),
        }
    for record in records:
        for index, value in enumerate(record["music"]["pitch_histogram"]):
            pitch_histogram[index] += value
        for index, value in enumerate(record["music"]["velocity_bin_histogram"]):
            velocity_histogram[index] += value

    result = {
        "schema_version": 1,
        "vocabulary_id": VOCABULARY_ID,
        "conditioning_vocabulary_id": CONDITIONING_VOCABULARY_ID,
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
        "performance_controls": performance_control_statistics,
        "sources": {
            "record_counts": dict(sorted(source_record_counts.items())),
        },
        "reproducibility": {
            "manifest_sha256": manifest_sha256 or "NOT_SUPPLIED",
            "inventory_sha256": inventory_sha256 or "NOT_SUPPLIED",
            "split_algorithm": "sha256(seed\\0source_id\\0source_revision) mod 10000",
            "vocabulary_id": VOCABULARY_ID,
        },
    }

    if manifest is not None:
        source_metadata = _manifest_source_metadata(manifest)
        record_source_ids = {str(record["source_id"]) for record in records}
        missing_sources = sorted(record_source_ids - set(source_metadata))
        if missing_sources:
            raise ValueError(
                "records reference source_id values absent from manifest: "
                + ", ".join(missing_sources)
            )
        result["provenance"] = {
            "manifest_id": manifest.get("manifest_id"),
            "status": manifest.get("status"),
            "source_count": len(source_metadata),
            "source_ids": sorted(source_metadata),
            "license_spdx_counts": dict(sorted(
                Counter(meta["spdx_id"] for meta in source_metadata.values()).items()
            )),
            "commercial_use_counts": dict(sorted(
                Counter(meta["commercial_use"] for meta in source_metadata.values()).items()
            )),
            "redistribution_counts": dict(sorted(
                Counter(meta["redistribution"] for meta in source_metadata.values()).items()
            )),
            "attribution_counts": dict(sorted(
                Counter(meta["attribution"] for meta in source_metadata.values()).items()
            )),
            "providers": dict(sorted(
                Counter(meta["provider"] for meta in source_metadata.values()).items()
            )),
            "unrepresented_manifest_sources": sorted(
                set(source_metadata) - record_source_ids
            ),
        }

    return result


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
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()

    if args.max_records_per_shard <= 0:
        print("ERROR: --max-records-per-shard must be positive", file=sys.stderr)
        return 1

    try:
        records = read_jsonl(args.input_jsonl)
        validate_records(records)
        manifest, effective_manifest_sha256, inventory_sha256 = _prepare_training_provenance(
            records,
            args.manifest,
            args.inventory,
            args.manifest_sha256,
        )
        paths = write_shards(
            records, args.output_dir, args.max_records_per_shard
        )
        stats_path = args.output_dir / "dataset-statistics.json"
        stats_path.write_text(
            json.dumps(
                _stats(
                    records,
                    effective_manifest_sha256,
                    manifest,
                    inventory_sha256,
                ),
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
