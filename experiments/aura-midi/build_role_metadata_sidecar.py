#!/usr/bin/env python3
"""Build a provenance-aware JSONL sidecar for the local MIDI corpora.

This utility reads paths/CSV/YAML metadata only. It deliberately does not import
PyTorch, load checkpoints, parse MIDI events, download data, or change tokenizers.
The sidecar is a research inventory, not permission to mix every source into a
production training run.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

SCHEMA_VERSION = 1
HEURISTIC_VERSION = "instrument_class_candidate_v1.0"
LICENSES = {
    "nrgcp": "CC BY 4.0",
    "gmd": "CC BY 4.0",
    "slakh2100_samples": "CC BY-NC 4.0",
    "maestro": "CC BY-NC-SA 4.0",
}
DEFAULT_OUTPUT = Path("experiments/aura-midi/runs/metadata-sidecar/role_metadata.jsonl")
DEFAULT_SUMMARY = Path("experiments/aura-midi/runs/metadata-sidecar/role_metadata_summary.json")
DEFAULT_REPORT = Path("experiments/aura-midi/audit_report.json")
MIDI_SUFFIXES = {".mid", ".midi"}


def norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def first_value(row: dict[str, Any], names: Iterable[str]) -> str | None:
    normalized = {norm_key(k): v for k, v in row.items()}
    for name in names:
        value = normalized.get(norm_key(name))
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def split_from(value: str | Path | None, fallback: str | None = None) -> str:
    if fallback:
        raw = norm_key(fallback)
        aliases = {"val": "validation", "valid": "validation", "dev": "validation"}
        raw = aliases.get(raw, raw)
        if raw in {"train", "validation", "test"}:
            return raw
    parts = [norm_key(p) for p in Path(str(value or "")).parts]
    for p in parts:
        if p in {"train", "training"}:
            return "train"
        if p in {"val", "valid", "validation", "dev"}:
            return "validation"
        if p in {"test", "testing"}:
            return "test"
    return "unknown"


def resolve_asset(raw_path: str | None, roots: Iterable[Path]) -> tuple[str | None, bool]:
    if not raw_path:
        return None, False
    candidate = Path(raw_path).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [root / candidate for root in roots]
    for item in candidates:
        try:
            resolved = item.resolve()
        except OSError:
            resolved = item
        if resolved.is_file():
            return str(resolved), True
    if candidate.is_absolute():
        return str(candidate), False
    first_root = next(iter(roots), Path.cwd())
    return str(first_root / candidate), False


def weak_role_candidate(instrument_class: str | None, is_drum: bool = False) -> tuple[str | None, float | None]:
    """Return a weak candidate, never a ground-truth functional role."""
    if is_drum:
        return "Drums", 0.80
    name = norm_key(instrument_class)
    if "drum" in name:
        return "Drums", 0.80
    if "bass" in name:
        return "Bass", 0.72
    if "synth_lead" in name or name in {"lead", "synthlead"}:
        return "Melody", 0.65
    if "synth_pad" in name or "strings" in name or "choir" in name or "atmosphere" in name:
        return "Atmosphere", 0.55
    if "chromatic_percussion" in name or "percussion" in name:
        return "Percussion", 0.60
    # Piano, guitar, organ, brass and other classes are functionally ambiguous.
    return None, None


def make_record(
    *, source_id: str, composition_id: str, asset_id: str, midi_path: str | None,
    asset_exists: bool, split: str, license_name: str, source_domain: str,
    source_role: str | None = None, role_origin: str = "unknown",
    role_kind: str = "functional_role", role_confidence: float | None = None,
    instrument_class: str | None = None, source_style: str | None = None,
    source_role_candidate: str | None = None, candidate_confidence: float | None = None,
    label_evidence: str = "unknown",
) -> dict[str, Any]:
    weak_label, weak_confidence = weak_role_candidate(instrument_class) if source_role_candidate is None else (source_role_candidate, candidate_confidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "source_version": "local-corpus-version-not-recorded",
        "composition_id": composition_id,
        "asset_id": asset_id,
        "midi_path": midi_path,
        "asset_exists": asset_exists,
        "split": split,
        "source_domain_label": source_domain,
        "instrument_class": instrument_class,
        "source_role_label": source_role,
        "source_role_kind": role_kind if source_role else None,
        "role_label_origin": role_origin if source_role else "unknown",
        "role_confidence": role_confidence if source_role else None,
        "role_evidence_level": label_evidence if source_role else "unknown",
        "weak_role_candidate": weak_label,
        "weak_role_confidence": weak_confidence,
        "heuristic_rule_version": HEURISTIC_VERSION if weak_label else None,
        "source_style_label": source_style,
        "genre_label": None,
        "genre_label_origin": "not_annotated",
        "genre_confidence": None,
        "section_label": None,
        "section_label_origin": "not_annotated",
        "license": license_name,
        "license_use_class": "noncommercial_only" if "NC" in license_name else "reported_cc_by_attribution_required_provenance_pending",
        "dedup_id": source_id + ":" + composition_id,
    }


def midi_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in MIDI_SUFFIXES)


def nrgcp_records(root: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = "nrgcp"
    if root is None or not root.is_dir():
        return [], {"status": "INPUT_NOT_FOUND", "path": str(root) if root else None}
    files = midi_files(root)
    records = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        # Keep relative parent directories: basenames can collide across folders.
        composition_id = Path(rel).with_suffix("").as_posix()
        records.append(make_record(
            source_id=source, composition_id=composition_id, asset_id=rel,
            midi_path=str(path.resolve()), asset_exists=True, split=split_from(rel),
            license_name=LICENSES[source], source_domain="algorithmic_edm_chord_progression",
            source_role="Chords/Harmony", role_origin="dataset_semantics",
            role_kind="musical_function", role_confidence=1.0,
            label_evidence="source_semantics",
        ))
    return records, {"status": "OK" if files else "NO_MIDI_FILES", "path": str(root), "files_seen": len(files)}


def csv_records(csv_path: Path | None, source: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if csv_path is None or not csv_path.is_file():
        return [], {"status": "INPUT_NOT_FOUND", "path": str(csv_path) if csv_path else None}
    records: list[dict[str, Any]] = []
    root = csv_path.parent
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        return [], {"status": "READ_ERROR", "path": str(csv_path), "error": str(exc)}
    for index, row in enumerate(rows):
        raw_path = first_value(row, ("midi_filename", "midi_file", "midi_path", "filename", "file_path", "path", "file"))
        split_raw = first_value(row, ("split", "dataset_split", "set", "subset", "partition"))
        path, exists = resolve_asset(raw_path, (root, root.parent, root.parent.parent))
        source_style = first_value(row, ("style", "rhythmic_style", "groove_style", "substyle"))
        if source == "gmd":
            explicit_id = first_value(row, ("groove_id", "example_id", "session_id"))
            composition = explicit_id or (Path(raw_path.replace("\\", "/")).with_suffix("").as_posix() if raw_path else f"row-{index:06d}")
            records.append(make_record(
                source_id=source, composition_id=composition, asset_id=raw_path or f"csv-row-{index}",
                midi_path=path, asset_exists=exists, split=split_from(raw_path, split_raw),
                license_name=LICENSES[source], source_domain="drum_groove",
                source_role="Drums", role_origin="dataset_semantics",
                role_kind="musical_function", role_confidence=1.0,
                source_style=source_style, label_evidence="source_semantics",
            ))
        else:
            explicit_id = first_value(row, ("composition_id", "title", "canonical_title"))
            composition = explicit_id or (Path(raw_path.replace("\\", "/")).with_suffix("").as_posix() if raw_path else f"row-{index:06d}")
            records.append(make_record(
                source_id=source, composition_id=composition, asset_id=raw_path or f"csv-row-{index}",
                midi_path=path, asset_exists=exists, split=split_from(raw_path, split_raw),
                license_name=LICENSES[source], source_domain="classical_solo_piano",
                source_role="Piano", role_origin="dataset_semantics",
                role_kind="instrument_identity_not_functional_role", role_confidence=1.0,
                instrument_class="Piano", label_evidence="source_semantics",
            ))
    return records, {"status": "OK", "path": str(csv_path), "rows_seen": len(rows), "rows_with_missing_midi": sum(not r["asset_exists"] for r in records)}


def slakh_records(root: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = "slakh2100_samples"
    if root is None or not root.is_dir():
        return [], {"status": "INPUT_NOT_FOUND", "path": str(root) if root else None}
    metadata_paths = sorted(root.rglob("metadata.yaml"))
    if not metadata_paths:
        return [], {"status": "NO_METADATA_YAML", "path": str(root), "files_seen": 0}
    if yaml is None:
        return [], {"status": "BLOCKED_MISSING_PYYAML", "path": str(root), "files_seen": 0}
    records: list[dict[str, Any]] = []
    for metadata_path in metadata_paths:
        rel_parts = metadata_path.relative_to(root).parts
        comp_name = next((p for p in rel_parts if re.fullmatch(r"Track\d+", p, re.IGNORECASE)), metadata_path.parent.name)
        try:
            loaded = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            continue
        stems = loaded.get("stems", {}) if isinstance(loaded, dict) else {}
        if not isinstance(stems, dict):
            continue
        comp_root = root / comp_name
        for stem_id, meta in stems.items():
            if not isinstance(meta, dict) or meta.get("midi_saved") is False:
                continue
            raw_instrument = meta.get("instrument_class") or meta.get("instrument") or meta.get("class")
            if not raw_instrument and isinstance(meta.get("program"), dict):
                raw_instrument = meta["program"].get("name")
            instrument_class = str(raw_instrument).strip() if raw_instrument else None
            matches = [p for p in comp_root.rglob("*") if p.is_file() and p.suffix.lower() in MIDI_SUFFIXES and (p.stem == str(stem_id) or p.stem.startswith(str(stem_id) + "_"))] if comp_root.is_dir() else []
            asset_path = str(matches[0].resolve()) if matches else None
            records.append(make_record(
                source_id=source, composition_id=comp_name, asset_id=str(stem_id),
                midi_path=asset_path, asset_exists=bool(matches),
                split=split_from(metadata_path), license_name=LICENSES[source],
                source_domain="multitrack_midi_stems", instrument_class=instrument_class,
                role_origin="instrument_class_heuristic",
            ))
    return records, {"status": "OK" if records else "NO_MIDI_SAVED_STEMS", "path": str(root), "metadata_files_seen": len(metadata_paths), "stems_seen": len(records), "stems_without_midi_path": sum(not r["asset_exists"] for r in records)}


def summarize(records: list[dict[str, Any]], inputs: dict[str, Any]) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_source[row["source_id"]].append(row)
    corpora = []
    for source in ("nrgcp", "gmd", "slakh2100_samples", "maestro"):
        rows = by_source.get(source, [])
        role_counts = Counter(r["source_role_label"] for r in rows if r.get("source_role_label"))
        candidate_counts = Counter(r["weak_role_candidate"] for r in rows if r.get("weak_role_candidate"))
        style_counts = Counter(r["source_style_label"] for r in rows if r.get("source_style_label"))
        compositions = {r["composition_id"] for r in rows}
        splits = Counter(r["split"] for r in rows)
        corpora.append({
            "source_name": source,
            "records": len(rows),
            "unique_compositions": len(compositions),
            "source_role_labels": dict(sorted(role_counts.items())),
            "weak_role_candidates": dict(sorted(candidate_counts.items())),
            "source_style_labels": dict(sorted(style_counts.items())),
            "splits": dict(sorted(splits.items())),
            "missing_asset_paths": sum(not r["asset_exists"] for r in rows),
            "genre_labeled_records": sum(bool(r.get("genre_label")) for r in rows),
            "license": LICENSES[source],
            "evidence_level": "VERIFIED_METADATA_SCAN" if inputs.get(source, {}).get("status") == "OK" else inputs.get(source, {}).get("status", "UNVERIFIED"),
        })
    return {
        "audit_date": date.today().isoformat(),
        "audit_type": "metadata-only role/genre sidecar inventory; no PyTorch, checkpoint loads, MIDI event parsing, training, or downloads",
        "schema_version": SCHEMA_VERSION,
        "sidecar_records": len(records),
        "inputs": inputs,
        "corpora": corpora,
        "coverage_gaps": {
            "trustworthy_electronic_subgenre_labels": sum(bool(r.get("genre_label")) for r in records) == 0,
            "reliable_arrangement_section_labels": sum(bool(r.get("section_label")) for r in records) == 0,
            "heuristic_role_candidates_are_not_ground_truth": True,
        },
        "evidence_policy": {
            "source_role_label": "Only source semantics or explicit source metadata; Piano is an instrument identity, not a functional arrangement role.",
            "weak_role_candidate": "Optional heuristic suggestion; always separate from source_role_label and versioned.",
            "source_style_label": "Preserves raw style tags such as GMD styles; not automatically promoted to electronic genre labels.",
            "unknown_values": "Missing labels, unknown splits and missing MIDI paths are preserved rather than guessed.",
        },
    }


def default_paths(data_root: Path) -> dict[str, Path | None]:
    gmd_csv = data_root / "gmd" / "extracted" / "groove" / "info.csv"
    maestro_csv = data_root / "maestro-v3.0.0" / "maestro-v3.0.0" / "maestro-v3.0.0.csv"
    slakh_root = data_root / "Slakh2100_samples"
    nrg_candidates = []
    if data_root.is_dir():
        for child in data_root.iterdir():
            key = norm_key(child.name)
            if child.is_dir() and "nrg" in key and "cp" in key:
                nrg_candidates.append(child)
    nrg_root = next((p for p in sorted(nrg_candidates) if midi_files(p)), None)
    return {
        "nrgcp_root": nrg_root or (nrg_candidates[0] if nrg_candidates else data_root / "nrgcp"),
        "gmd_csv": gmd_csv,
        "maestro_csv": maestro_csv,
        "slakh_root": slakh_root,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("experiments/aura-midi/datasets"))
    parser.add_argument("--nrgcp-root", type=Path)
    parser.add_argument("--gmd-csv", type=Path)
    parser.add_argument("--maestro-csv", type=Path)
    parser.add_argument("--slakh-root", type=Path)
    parser.add_argument("--sidecar-out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    defaults = default_paths(args.data_root)
    paths = {
        "nrgcp_root": args.nrgcp_root or defaults["nrgcp_root"],
        "gmd_csv": args.gmd_csv or defaults["gmd_csv"],
        "maestro_csv": args.maestro_csv or defaults["maestro_csv"],
        "slakh_root": args.slakh_root or defaults["slakh_root"],
    }
    records: list[dict[str, Any]] = []
    inputs: dict[str, Any] = {}
    new, inputs["nrgcp"] = nrgcp_records(paths["nrgcp_root"])
    records.extend(new)
    new, inputs["gmd"] = csv_records(paths["gmd_csv"], "gmd")
    records.extend(new)
    new, inputs["slakh2100_samples"] = slakh_records(paths["slakh_root"])
    records.extend(new)
    new, inputs["maestro"] = csv_records(paths["maestro_csv"], "maestro")
    records.extend(new)

    # A missing/partial local source is reported, not fabricated or silently called complete.
    seen = set()
    deduped = []
    duplicates = 0
    for row in records:
        key = (row["source_id"], row["asset_id"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        deduped.append(row)
    records = deduped

    args.sidecar_out.parent.mkdir(parents=True, exist_ok=True)
    with args.sidecar_out.open("w", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = summarize(records, inputs)
    summary["sidecar_path"] = str(args.sidecar_out)
    summary["duplicate_asset_rows_removed"] = duplicates
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Preserve Phase 1 training facts from the previously generated report.
    previous: dict[str, Any] = {}
    if args.report_out.is_file():
        try:
            previous = json.loads(args.report_out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    report = dict(previous)
    report.update({
        "audit_date": date.today().isoformat(),
        "audit_type": "metadata-only inventory + role metadata JSONL (reproducible local scan)",
        "metadata_sidecar": str(args.sidecar_out),
        "metadata_sidecar_summary": str(args.summary_out),
        "sidecar_records": len(records),
        "sidecar_inputs": inputs,
        "sidecar_corpora": summary["corpora"],
        "sidecar_coverage_gaps": summary["coverage_gaps"],
        "duplicate_asset_rows_removed": duplicates,
    })
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "sidecar_path": str(args.sidecar_out),
        "sidecar_records": len(records),
        "summary_path": str(args.summary_out),
        "report_path": str(args.report_out),
        "inputs": inputs,
        "corpora": summary["corpora"],
        "note": "Check INPUT_NOT_FOUND, NO_MIDI_FILES, missing asset paths and unknown splits before treating counts as complete.",
    }, ensure_ascii=False, indent=2))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())
