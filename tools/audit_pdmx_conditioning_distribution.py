#!/usr/bin/env python3
"""Audit retrospective performance-control distributions on a deterministic PDMX sample.

This is a development/QA report only. It must never be used to create training
conditioning labels: the current control extractor is retrospective and may
depend on target MIDI events. Production training still requires independent
intent/context labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from midi_smf import MidiValidationError
from midi_normalize import normalize_smf
from mozart_conditioning import (
    PERFORMANCE_CONTROL_NAMES,
    derive_performance_controls,
)


NA_VALUES = {"", "n/a", "na", "none", "null"}
TRUE_VALUES = {"1", "true", "yes", "y", "t"}


def normalize_relpath(value: str, *, prefix: str | None = None) -> str:
    raw = str(value).strip().replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"unsafe relative path: {value!r}")
    normalized = "/".join(parts)
    if normalized.startswith("/"):
        raise ValueError(f"unsafe relative path: {value!r}")
    if prefix:
        prefix = prefix.strip("/")
        if not normalized.casefold().startswith(prefix.casefold() + "/"):
            normalized = f"{prefix}/{normalized}"
    return normalized


def is_na(value: str) -> bool:
    return str(value).strip().lower() in NA_VALUES


def is_true(value: str) -> bool:
    return str(value).strip().lower() in TRUE_VALUES


def load_subset(path: Path) -> set[str]:
    values: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        values.add(normalize_relpath(value, prefix="data"))
    if not values:
        raise ValueError(f"{path}: subset manifest is empty")
    return values


def select_candidates(
    csv_path: Path,
    subset: set[str],
    *,
    sample_size: int,
    sample_seed: str,
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    rows = 0
    subset_rows = 0
    candidates: list[tuple[str, str]] = []
    seen_paths: set[str] = set()

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "path",
            "mid",
            "license",
            "license_url",
            "subset:no_license_conflict",
        }
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(
                "PDMX.csv missing required columns: " + ", ".join(missing)
            )

        for row in reader:
            rows += 1
            data_path = normalize_relpath(row["path"], prefix="data")
            if data_path in seen_paths:
                raise ValueError(f"duplicate PDMX path: {data_path}")
            seen_paths.add(data_path)

            if is_true(row["subset:no_license_conflict"]):
                subset_rows += 1
            if data_path not in subset:
                continue
            if not is_true(row["subset:no_license_conflict"]):
                raise ValueError(
                    f"subset manifest contains row not flagged no_license_conflict: {data_path}"
                )
            if is_na(row["mid"]):
                continue
            if is_na(row["license"]) or is_na(row["license_url"]):
                continue

            mid_path = normalize_relpath(row["mid"], prefix="mid")
            candidates.append((mid_path, data_path))

    if not candidates:
        raise ValueError("no recommended PDMX MIDI candidates found")

    # A PDMX metadata row may theoretically reference the same MIDI path more
    # than once. The preflight measures MIDI files, not metadata-row aliases,
    # so collapse duplicate MIDI paths deterministically.
    unique_candidates: dict[str, str] = {}
    for mid_path, data_path in candidates:
        unique_candidates.setdefault(mid_path, data_path)

    ranked = sorted(
        unique_candidates.items(),
        key=lambda item: hashlib.sha256(
            f"{sample_seed}\0{item[0]}".encode("utf-8")
        ).hexdigest(),
    )
    selected = ranked[: min(sample_size, len(ranked))]
    return selected, {
        "csv_rows": rows,
        "csv_no_license_conflict_rows": subset_rows,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
    }


def summarize(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty value list")
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "non_zero_fraction": sum(value != 0.0 for value in values) / len(values),
    }


def audit(
    csv_path: Path,
    subset_path: Path,
    midi_source: Path,
    *,
    sample_size: int = 1024,
    sample_seed: str = "mozart-pdmx-conditioning-v1",
) -> dict:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")

    subset = load_subset(subset_path)
    selected, selection = select_candidates(
        csv_path,
        subset,
        sample_size=sample_size,
        sample_seed=sample_seed,
    )
    selected_by_mid = {
        mid_path: data_path
        for mid_path, data_path in selected
    }

    successes: list[tuple[str, str, dict[str, float]]] = []
    failures: list[dict[str, str]] = []
    seen_mid: set[str] = set()

    with tarfile.open(midi_source, "r:*") as archive:
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(
                    f"MIDI archive contains non-regular member: {member.name}"
                )

            mid_path = normalize_relpath(member.name, prefix="mid")
            data_path = selected_by_mid.get(mid_path)
            if data_path is None:
                continue

            if mid_path in seen_mid:
                raise ValueError(f"duplicate MIDI path in archive: {mid_path}")
            seen_mid.add(mid_path)

            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"cannot read MIDI member: {mid_path}")

            try:
                normalized = normalize_smf(handle.read(), quantize=False)
                notes = [
                    {
                        "start_beat": note.start_beat,
                        "duration_beats": note.duration_beats,
                        "note": note.note,
                        "velocity": note.velocity,
                        "channel": note.channel,
                    }
                    for note in normalized.notes
                ]
                controls = derive_performance_controls(
                    notes,
                    normalized.length_beats,
                )
                successes.append((mid_path, data_path, controls))
            except (MidiValidationError, ValueError) as exc:
                failures.append(
                    {
                        "mid_path": mid_path,
                        "data_path": data_path,
                        "error": str(exc),
                    }
                )

    missing = sorted(set(selected_by_mid) - seen_mid)
    if missing:
        raise ValueError(
            f"selected MIDI candidates missing from archive: {len(missing)}"
        )

    successful_by_control: dict[str, list[float]] = {
        name: [] for name in PERFORMANCE_CONTROL_NAMES
    }
    for _, _, controls in successes:
        for name in PERFORMANCE_CONTROL_NAMES:
            successful_by_control[name].append(float(controls[name]))

    distribution: dict[str, dict] = {}
    for name in PERFORMANCE_CONTROL_NAMES:
        if name == "swing":
            distribution[name] = {
                "status": "NOT_MEASURED",
                "reason": (
                    "The current retrospective derive_performance_controls() "
                    "implementation returns swing=0.0 and does not infer swing timing."
                ),
            }
            continue
        values = successful_by_control[name]
        distribution[name] = (
            {"status": "NO_SUCCESSFUL_SAMPLES"}
            if not values
            else {"status": "MEASURED", **summarize(values)}
        )

    return {
        "schema_version": 1,
        "status": "PASS" if successes else "NO_SUCCESSFUL_SAMPLES",
        "purpose": "development_qa_only",
        "source": {
            "csv": str(csv_path),
            "subset": str(subset_path),
            "midi_source": str(midi_source),
            "sample_seed": sample_seed,
            "sample_size_requested": sample_size,
        },
        "selection": selection,
        "results": {
            "successful_samples": len(successes),
            "failed_samples": len(failures),
            "missing_from_archive": len(missing),
            "controls": distribution,
        },
        "quality_notes": [
            "Retrospective controls are diagnostic only and must not become training labels.",
            "MIDI normalization is run with quantize=False so timing-derived QA is not erased before measurement.",
            "Swing is explicitly NOT_MEASURED by the current retrospective extractor.",
        ],
        "failures": failures[:32],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("subset", type=Path)
    parser.add_argument("midi_source", type=Path)
    parser.add_argument("--sample-size", type=int, default=1024)
    parser.add_argument(
        "--sample-seed",
        default="mozart-pdmx-conditioning-v1",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = audit(
            args.csv,
            args.subset,
            args.midi_source,
            sample_size=args.sample_size,
            sample_seed=args.sample_seed,
        )
    except (OSError, ValueError, csv.Error, tarfile.TarError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: "
        f"selected={result['selection']['selected_count']} "
        f"successful={result['results']['successful_samples']} "
        f"failed={result['results']['failed_samples']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
