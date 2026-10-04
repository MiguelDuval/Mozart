#!/usr/bin/env python3
"""Audit the PDMX metadata/subset/MIDI path contract without committing dataset bytes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import posixpath
import tarfile
from pathlib import Path


REQUIRED_COLUMNS = {
    "path",
    "metadata",
    "mxl",
    "pdf",
    "mid",
    "license",
    "license_url",
    "license_conflict",
    "subset:no_license_conflict",
    "subset:all_valid",
}
TRUE_VALUES = {"1", "true", "yes", "y", "t"}
NA_VALUES = {"", "n/a", "na", "none", "null"}


def normalize_relpath(value: str, *, prefix: str | None = None) -> str:
    raw = str(value).strip().replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    raw = posixpath.normpath(raw)
    if raw in {"", "."} or raw.startswith("/") or raw == ".." or raw.startswith("../"):
        raise ValueError(f"unsafe relative path: {value!r}")
    if any(part == ".." for part in raw.split("/")):
        raise ValueError(f"unsafe relative path: {value!r}")
    if prefix:
        prefix = prefix.strip("/").lower()
        lower = raw.lower()
        if lower.startswith(prefix + "/"):
            return raw
        return f"{prefix}/{raw}"
    return raw


def is_true(value: str) -> bool:
    return str(value).strip().lower() in TRUE_VALUES


def is_na(value: str) -> bool:
    return str(value).strip().lower() in NA_VALUES


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def inventory_midi(source: Path, *, expected_prefix: str = "mid") -> dict[str, dict]:
    entries: dict[str, dict] = {}

    if source.is_dir():
        root = source.resolve()
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"symlink is not allowed in MIDI source: {path}")
            if not path.is_file():
                if path.exists():
                    continue
                raise ValueError(f"broken MIDI source entry: {path}")
            rel = path.relative_to(root).as_posix()
            archive_path = normalize_relpath(rel, prefix=expected_prefix)
            if not archive_path.lower().endswith((".mid", ".midi")):
                raise ValueError(f"non-MIDI file in MIDI source: {archive_path}")
            digest, size = _hash_file(path)
            if archive_path in entries:
                raise ValueError(f"duplicate MIDI path: {archive_path}")
            entries[archive_path] = {
                "path": archive_path,
                "sha256": digest,
                "size_bytes": size,
            }
        return entries

    with tarfile.open(source, "r:*") as tf:
        for member in tf:
            if not member.isfile():
                raise ValueError(f"MIDI archive contains non-regular member: {member.name}")
            archive_path = normalize_relpath(member.name)
            if archive_path.lower().startswith("mid/"):
                normalized = archive_path
            else:
                normalized = normalize_relpath(archive_path, prefix=expected_prefix)
            if not normalized.lower().endswith((".mid", ".midi")):
                raise ValueError(f"non-MIDI file in MIDI archive: {normalized}")
            if normalized in entries:
                raise ValueError(f"duplicate MIDI path: {normalized}")
            handle = tf.extractfile(member)
            if handle is None:
                raise ValueError(f"cannot read MIDI member: {normalized}")
            digest = hashlib.sha256()
            size = 0
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
            entries[normalized] = {
                "path": normalized,
                "sha256": digest.hexdigest(),
                "size_bytes": size,
            }
    return entries


def canonical_inventory_digest(entries: dict[str, dict]) -> str:
    ordered = [entries[key] for key in sorted(entries)]
    payload = json.dumps(
        ordered,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def audit(
    csv_path: Path,
    subset_path: Path,
    *,
    midi_source: Path | None = None,
    output: Path | None = None,
) -> dict:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError("PDMX.csv missing required columns: " + ", ".join(missing))

        rows = 0
        no_license_conflict = set()
        no_license_conflict_with_mid = set()
        all_mid_paths_from_csv = set()
        license_conflicts = 0
        subset_flag_conflicts = 0
        recommended_rows_missing_license_metadata = 0
        rows_with_mid = 0
        row_paths = set()

        for row in reader:
            rows += 1
            path = normalize_relpath(row["path"], prefix="data")
            if path in row_paths:
                raise ValueError(f"duplicate PDMX path: {path}")
            row_paths.add(path)

            conflict = is_true(row["license_conflict"])
            subset_flag = is_true(row["subset:no_license_conflict"])
            if conflict:
                license_conflicts += 1
            if subset_flag and conflict:
                subset_flag_conflicts += 1
            if subset_flag:
                no_license_conflict.add(path)
                if is_na(row["license"]) or is_na(row["license_url"]):
                    recommended_rows_missing_license_metadata += 1

            mid_value = row["mid"]
            if not is_na(mid_value):
                rows_with_mid += 1
                mid_path = normalize_relpath(mid_value, prefix="mid")
                all_mid_paths_from_csv.add(mid_path)
                if subset_flag:
                    no_license_conflict_with_mid.add(mid_path)

        subset_paths = set()
        for line in subset_path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            subset_paths.add(normalize_relpath(value, prefix="data"))

        result = {
            "schema_version": 1,
            "rows": rows,
            "license_conflicts": license_conflicts,
            "subset_flag_conflicts": subset_flag_conflicts,
            "recommended_rows_missing_license_metadata": recommended_rows_missing_license_metadata,
            "no_license_conflict_rows": len(no_license_conflict),
            "rows_with_mid": rows_with_mid,
            "no_license_conflict_rows_with_mid": len(no_license_conflict_with_mid),
            "subset_file_rows": len(subset_paths),
            "subset_csv_exact_match": no_license_conflict == subset_paths,
            "subset_paths_missing_from_csv": len(subset_paths - row_paths),
            "csv_subset_rows_missing_from_subset_file": len(no_license_conflict - subset_paths),
            "midi_source": None,
            "midi_inventory": None,
        }

        if midi_source is not None:
            inventory = inventory_midi(midi_source)
            expected_mid = no_license_conflict_with_mid
            actual_mid = set(inventory)
            result["midi_source"] = str(midi_source)
            result["midi_inventory"] = {
                "file_count": len(actual_mid),
                "total_bytes": sum(item["size_bytes"] for item in inventory.values()),
                "inventory_sha256": canonical_inventory_digest(inventory),
                "csv_mid_count": len(all_mid_paths_from_csv),
                "csv_mid_exact_match": actual_mid == all_mid_paths_from_csv,
                "unexpected_mid_files": len(actual_mid - all_mid_paths_from_csv),
                "missing_csv_mid_files": len(all_mid_paths_from_csv - actual_mid),
                "expected_no_license_conflict_mid_count": len(expected_mid),
                "no_license_conflict_mid_all_present": expected_mid <= actual_mid,
                "subset_mid_outside_inventory": len(expected_mid - actual_mid),
            }

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("subset_paths", type=Path)
    parser.add_argument("--midi-source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        result = audit(
            args.csv,
            args.subset_paths,
            midi_source=args.midi_source,
            output=args.output,
        )
    except (OSError, ValueError, csv.Error) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(
        "PASS: "
        f"rows={result['rows']} "
        f"no_license_conflict={result['no_license_conflict_rows']} "
        f"no_license_conflict_with_mid={result['no_license_conflict_rows_with_mid']}"
    )
    if result["midi_inventory"] is not None:
        mi = result["midi_inventory"]
        print(
            "MIDI: "
            f"files={mi['file_count']} "
            f"inventory_sha256={mi['inventory_sha256']} "
            f"csv_mid_exact_match={mi['csv_mid_exact_match']} "
            f"subset_mid_all_present={mi['no_license_conflict_mid_all_present']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
