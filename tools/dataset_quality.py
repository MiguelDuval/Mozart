#!/usr/bin/env python3
"""Produce a deterministic QA/rejection report for Mozart training records."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_split import source_key
from build_training_shards import SPLITS, VOCABULARY_ID, VOCABULARY_SIZE, read_jsonl


def record_reasons(record: object) -> list[str]:
    reasons: list[str] = []
    if not isinstance(record, dict):
        return ["record_not_object"]

    if record.get("schema_version") != 1:
        reasons.append("invalid_schema_version")
    if record.get("vocabulary_id") != VOCABULARY_ID:
        reasons.append("invalid_vocabulary_id")
    if record.get("vocabulary_size") != VOCABULARY_SIZE:
        reasons.append("invalid_vocabulary_size")

    for key in ("source_id", "source_revision"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"missing_{key}")

    if record.get("split") not in SPLITS:
        reasons.append("invalid_split")

    tokens = record.get("tokens")
    if not isinstance(tokens, list) or not tokens:
        reasons.append("missing_tokens")
    elif (
        any(
            not isinstance(token, int) or not 0 <= token < VOCABULARY_SIZE
            for token in tokens
        )
    ):
        reasons.append("token_out_of_range")
    else:
        if tokens[0] != 1:
            reasons.append("missing_bos")
        if tokens[-1] != 2:
            reasons.append("missing_eos")
        if len(tokens) > 16384:
            reasons.append("token_budget_exceeded")

    music = record.get("music")
    if not isinstance(music, dict):
        reasons.append("missing_music")
    else:
        bars = music.get("length_bars")
        if not isinstance(bars, int) or not 4 <= bars <= 16:
            reasons.append("invalid_bar_length")

        note_count = music.get("note_event_count")
        if not isinstance(note_count, int) or not 0 <= note_count <= 4096:
            reasons.append("note_event_budget_exceeded")

        control_count = music.get("controller_event_count")
        if not isinstance(control_count, int) or not 0 <= control_count <= 1024:
            reasons.append("controller_event_budget_exceeded")

        polyphony = music.get("max_start_step_polyphony")
        if not isinstance(polyphony, int) or polyphony < 0:
            reasons.append("invalid_polyphony")

        pitch_histogram = music.get("pitch_histogram")
        if (
            not isinstance(pitch_histogram, list)
            or len(pitch_histogram) != 128
            or not all(isinstance(value, int) and value >= 0 for value in pitch_histogram)
            or (isinstance(note_count, int) and sum(pitch_histogram) != note_count)
        ):
            reasons.append("invalid_pitch_histogram")

        velocity_histogram = music.get("velocity_bin_histogram")
        if (
            not isinstance(velocity_histogram, list)
            or len(velocity_histogram) != 32
            or not all(isinstance(value, int) and value >= 0 for value in velocity_histogram)
            or (isinstance(note_count, int) and sum(velocity_histogram) != note_count)
        ):
            reasons.append("invalid_velocity_histogram")

        if (
            isinstance(note_count, int)
            and isinstance(control_count, int)
            and note_count + control_count == 0
        ):
            reasons.append("no_usable_musical_events")

    conditioning = record.get("conditioning")
    if not isinstance(conditioning, dict):
        reasons.append("missing_conditioning")
    else:
        for key in ("style", "substyle", "mood", "rhythm", "role"):
            value = conditioning.get(key)
            if not isinstance(value, str) or not value.strip():
                reasons.append(f"missing_conditioning_{key}")

    return reasons


def duplicate_key(record: dict) -> str:
    payload = {
        "tokens": record.get("tokens"),
        "conditioning": record.get("conditioning"),
        "music": record.get("music"),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_duplicate_reviews(path: Path) -> dict[str, dict[str, str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read duplicate review {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("duplicate review must be an object with schema_version=1")
    reviews = value.get("reviews")
    if not isinstance(reviews, dict):
        raise ValueError("duplicate review.reviews must be an object")
    normalized: dict[str, dict[str, str]] = {}
    for digest, review in reviews.items():
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdefABCDEF" for ch in digest)
        ):
            raise ValueError("duplicate review keys must be SHA-256 digests")
        if not isinstance(review, dict):
            raise ValueError(f"duplicate review for {digest} must be an object")
        decision = review.get("decision")
        if decision not in {"intentional", "exclude"}:
            raise ValueError(
                f"duplicate review decision for {digest} must be intentional or exclude"
            )
        normalized[digest.lower()] = {"decision": decision}
    return normalized

def build_report(
    records: list[object],
    *,
    manifest_sha256: str | None = None,
    duplicate_reviews: dict[str, dict[str, str]] | None = None,
) -> dict:
    reason_counts = Counter()
    split_counts = Counter()
    duplicate_groups: dict[str, list[int]] = defaultdict(list)
    source_splits: dict[str, set[str]] = defaultdict(set)

    accepted = 0
    for index, record in enumerate(records):
        reasons = record_reasons(record)
        if reasons:
            for reason in reasons:
                reason_counts[reason] += 1
        else:
            accepted += 1

        if isinstance(record, dict):
            split = record.get("split")
            if split in SPLITS:
                split_counts[str(split)] += 1
            try:
                group = source_key(record)
            except ValueError:
                group = None
            if group is not None and split in SPLITS:
                source_splits[group].add(str(split))
            if not reasons:
                duplicate_groups[duplicate_key(record)].append(index)

    cross_split_groups = sorted(
        group
        for group, splits in source_splits.items()
        if len(splits) > 1
    )
    for _group in cross_split_groups:
        reason_counts["source_group_crosses_split"] += 1

    duplicate_candidates = [
        {"sha256": digest, "record_indexes": indexes}
        for digest, indexes in sorted(duplicate_groups.items())
        if len(indexes) > 1
    ]
    if duplicate_candidates:
        reason_counts["duplicate_content_candidate"] += len(duplicate_candidates)

    return {
        "schema_version": 1,
        "vocabulary_id": VOCABULARY_ID,
        "record_count": len(records),
        "accepted_count": accepted,
        "rejected_count": len(records) - accepted,
        "split_counts": {split: split_counts.get(split, 0) for split in SPLITS},
        "rejection_reasons": dict(sorted(reason_counts.items())),
        "source_groups_crossing_splits": cross_split_groups,
        "duplicate_content_candidates": duplicate_candidates,
        "reproducibility": {
            "manifest_sha256": manifest_sha256 or "NOT_SUPPLIED",
            "report_algorithm": "mozart-dataset-quality-v1",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    try:
        records = read_jsonl(args.input_jsonl)
        report = build_report(records, manifest_sha256=args.manifest_sha256)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: QA report records={report['record_count']} "
        f"accepted={report['accepted_count']} rejected={report['rejected_count']}"
    )
    if args.strict and (
        report["rejected_count"]
        or report["source_groups_crossing_splits"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
