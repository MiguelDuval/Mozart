#!/usr/bin/env python3
"""Build a deterministic fixture for compositional categorical conditioning.

Development-only: training exposes one categorical axis at a time. Validation
and test records require unseen combinations of multiple categorical axes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_fixture_corpus import make_smf, sha256_file
from midi_to_training_example import build_example
from mozart_conditioning import validate_conditioning

FIXTURE_REVISION = "mozart-categorical-composition-fixture-v1"
BASE_CONDITIONING = {
    "style": "electronic",
    "substyle": "generic",
    "mood": "neutral",
    "rhythm": "straight",
    "role": "bass",
}
NEUTRAL_CONTROLS = {
    "density": 0.5,
    "energy": 0.5,
    "syncopation": 0.5,
    "swing": 0.5,
    "variation": 0.5,
}
HIGH_VALUES = {
    "style": "dark_techno",
    "substyle": "dark_techno",
    "mood": "hypnotic",
    "rhythm": "syncopated",
    "role": "lead",
}
TRAIN_CONTEXTS = (101, 707)
VALIDATION_CONTEXTS = (3001, 3002)
SPARSE_TRAINING_COMPOSITIONS = (
    ("style+substyle", ("style", "substyle")),
    ("style+role", ("style", "role")),
    ("substyle+mood", ("substyle", "mood")),
    ("mood+role", ("mood", "role")),
    ("substyle+rhythm", ("substyle", "rhythm")),
    ("rhythm+role", ("rhythm", "role")),
)
MATCHED_SINGLE_AXIS_EXTRA_RECORDS = (
    ("style", "high", 1311),
    ("style", "high", 2713),
    ("substyle", "high", 1311),
    ("substyle", "high", 2713),
    ("mood", "high", 1311),
    ("mood", "high", 2713),
    ("rhythm", "high", 1311),
    ("rhythm", "high", 2713),
    ("role", "high", 1311),
    ("role", "high", 2713),
    ("base", "base", 1311),
    ("base", "base", 2713),
)
PAIRWISE_TRAINING_COMPOSITIONS = (
    ("style+substyle", ("style", "substyle")),
    ("style+mood", ("style", "mood")),
    ("style+rhythm", ("style", "rhythm")),
    ("style+role", ("style", "role")),
    ("substyle+mood", ("substyle", "mood")),
    ("substyle+rhythm", ("substyle", "rhythm")),
    ("substyle+role", ("substyle", "role")),
    ("mood+rhythm", ("mood", "rhythm")),
    ("mood+role", ("mood", "role")),
    ("rhythm+role", ("rhythm", "role")),
)

TEST_CONTEXT = 1901
COMPOSITIONS = (
    ("style+rhythm", ("style", "rhythm")),
    ("style+mood", ("style", "mood")),
    ("substyle+role", ("substyle", "role")),
    ("mood+rhythm+role", ("mood", "rhythm", "role")),
    ("style+substyle+mood", ("style", "substyle", "mood")),
    ("style+rhythm+role", ("style", "rhythm", "role")),
    ("substyle+mood+rhythm", ("substyle", "mood", "rhythm")),
    ("all-five", ("style", "substyle", "mood", "rhythm", "role")),
    ("style+mood+role", ("style", "mood", "role")),
    ("substyle+rhythm+role", ("substyle", "rhythm", "role")),
)


def render_notes(conditioning: dict[str, str], *, context_seed: int) -> list[list[tuple[int, int, int, int]]]:
    """Render four bars; bar 0 is always neutral shared context."""
    notes: list[list[tuple[int, int, int, int]]] = []
    for bar in range(4):
        active = BASE_CONDITIONING if bar == 0 else conditioning
        bar_seed = context_seed + bar * 17
        role_shift = 24 if active["role"] == "lead" else 0
        style_shift = 1 if active["style"] == "dark_techno" else 0
        substyle_shift = 2 if active["substyle"] == "dark_techno" else 0
        mood_shift = 3 if active["mood"] == "hypnotic" else 0

        bar_notes: list[tuple[int, int, int, int]] = []
        for index in range(6):
            step = (index * 3 + bar_seed) % 16
            if active["rhythm"] == "syncopated" and index % 2:
                step = (step + 1) % 16
            pitch = (
                36
                + role_shift
                + style_shift
                + substyle_shift
                + mood_shift
                + ((index * 2 + bar_seed) % 7)
            )
            velocity = 72 + ((index + bar_seed) % 5) * 4
            duration = min(1 + ((index + bar_seed) % 3), max(1, 16 - step))
            bar_notes.append((pitch, step * 120, duration * 120, velocity))
        bar_notes.sort(key=lambda item: (item[1], item[0]))
        notes.append(bar_notes)
    return notes


def _conditioning(axes: tuple[str, ...]) -> dict[str, str]:
    result = dict(BASE_CONDITIONING)
    for axis in axes:
        if axis not in HIGH_VALUES:
            raise ValueError(f"unsupported composition axis: {axis}")
        result[axis] = HIGH_VALUES[axis]
    validate_conditioning(**result, seed=0)
    return result


def _record(
    output_dir: Path,
    *,
    source_id: str,
    split: str,
    conditioning: dict[str, str],
    context_seed: int,
    profile: str,
    fixture_revision: str = FIXTURE_REVISION,
) -> dict:
    validate_conditioning(**conditioning, seed=0)
    filename = f"{profile.replace('+', '-')}-context-{context_seed}.mid"
    midi_path = output_dir / "midi" / filename
    midi_path.write_bytes(
        make_smf(
            bars=4,
            beats_per_bar=4,
            notes_by_bar=render_notes(conditioning, context_seed=context_seed),
        )
    )
    record = build_example(
        midi_path,
        source_id=source_id,
        source_revision=fixture_revision,
        source_path=f"midi/{filename}",
        **conditioning,
        seed=50000 + context_seed,
        performance_controls=NEUTRAL_CONTROLS,
    )
    record.update(
        {
            "split": split,
            "target_sha256": sha256_file(midi_path),
            "composition_profile": profile,
            "composition_axes": [axis for axis in HIGH_VALUES if conditioning[axis] != BASE_CONDITIONING[axis]],
            "context_seed": context_seed,
        }
    )
    return record


def build_fixture(output_dir: Path, *, training_profile: str = "single-axis-only") -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "midi").mkdir()

    if training_profile not in {
        "single-axis-only",
        "matched-single-axis-32",
        "sparse-multi-axis",
        "pairwise-multi-axis-40",
    }:
        raise ValueError(f"unsupported training profile: {training_profile!r}")
    fixture_revision_suffixes = {
        "single-axis-only": "",
        "matched-single-axis-32": "-matched-single-axis-32",
        "sparse-multi-axis": "-sparse-coverage",
        "pairwise-multi-axis-40": "-pairwise-40",
    }
    fixture_revision = f"{FIXTURE_REVISION}{fixture_revision_suffixes[training_profile]}"

    records: list[dict] = []

    for axis in HIGH_VALUES:
        for value_label, value in (("base", BASE_CONDITIONING[axis]), ("high", HIGH_VALUES[axis])):
            conditioning = dict(BASE_CONDITIONING)
            conditioning[axis] = value
            for context_seed in TRAIN_CONTEXTS:
                records.append(
                    _record(
                        output_dir,
                        source_id=f"composition-train-{axis}-{value_label}-{context_seed}",
                        split="train",
                        conditioning=conditioning,
                        context_seed=context_seed,
                        profile=f"single-{axis}-{value_label}",
                        fixture_revision=fixture_revision,
                    )
                )

    if training_profile == "matched-single-axis-32":
        for index, (axis, value_label, context_seed) in enumerate(MATCHED_SINGLE_AXIS_EXTRA_RECORDS):
            if axis == "base":
                conditioning = dict(BASE_CONDITIONING)
                profile = "matched-base-extra"
            else:
                conditioning = dict(BASE_CONDITIONING)
                conditioning[axis] = HIGH_VALUES[axis]
                profile = f"matched-single-{axis}-high"
            records.append(
                _record(
                    output_dir,
                    source_id=f"composition-train-matched-extra-{index}",
                    split="train",
                    conditioning=conditioning,
                    context_seed=context_seed,
                    profile=profile,
                    fixture_revision=fixture_revision,
                )
            )

    if training_profile == "pairwise-multi-axis-40":
        for profile, axes in PAIRWISE_TRAINING_COMPOSITIONS:
            for context_seed in TRAIN_CONTEXTS:
                records.append(
                    _record(
                        output_dir,
                        source_id=f"composition-train-{profile}-{context_seed}",
                        split="train",
                        conditioning=_conditioning(axes),
                        context_seed=context_seed,
                        profile=f"train-{profile}",
                        fixture_revision=fixture_revision,
                    )
                )
    if training_profile == "sparse-multi-axis":
        held_out_axis_sets = {frozenset(axes) for _, axes in COMPOSITIONS}
        for profile, axes in SPARSE_TRAINING_COMPOSITIONS:
            if frozenset(axes) in held_out_axis_sets:
                raise RuntimeError(f"sparse training composition overlaps held-out profile: {profile}")
            for context_seed in TRAIN_CONTEXTS:
                records.append(
                    _record(
                        output_dir,
                        source_id=f"composition-train-{profile}-{context_seed}",
                        split="train",
                        conditioning=_conditioning(axes),
                        context_seed=context_seed,
                        profile=f"train-{profile}",
                        fixture_revision=fixture_revision,
                    )
                )

    for index, (profile, axes) in enumerate(COMPOSITIONS):
        records.append(
            _record(
                output_dir,
                source_id=f"composition-validation-{index}",
                split="validation",
                conditioning=_conditioning(axes),
                context_seed=VALIDATION_CONTEXTS[index % len(VALIDATION_CONTEXTS)],
                profile=profile,
                fixture_revision=fixture_revision,
            )
        )

    test_records = []
    for index, (profile, axes) in enumerate(COMPOSITIONS):
        test_records.append(
            _record(
                output_dir,
                source_id=f"composition-test-base-{index}",
                split="test",
                conditioning=dict(BASE_CONDITIONING),
                context_seed=TEST_CONTEXT,
                profile=f"{profile}-base",
                fixture_revision=fixture_revision,
            )
        )
        test_records.append(
            _record(
                output_dir,
                source_id=f"composition-test-{index}",
                split="test",
                conditioning=_conditioning(axes),
                context_seed=TEST_CONTEXT,
                profile=profile,
                fixture_revision=fixture_revision,
            )
        )
    records.extend(test_records)

    counts = {
        split: sum(record["split"] == split for record in records)
        for split in ("train", "validation", "test")
    }
    expected_train_counts = {
        "single-axis-only": 20,
        "matched-single-axis-32": 32,
        "sparse-multi-axis": 32,
        "pairwise-multi-axis-40": 40,
    }
    expected_counts = {
        "train": expected_train_counts[training_profile],
        "validation": 10,
        "test": 20,
    }
    expected_total = sum(expected_counts.values())
    if len(records) != expected_total or counts != expected_counts:
        raise RuntimeError(f"unexpected composition fixture shape: records={len(records)} splits={counts}")

    (output_dir / "records.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    for split in ("train", "validation", "test"):
        selected = [record for record in records if record["split"] == split]
        (output_dir / f"{split}.jsonl").write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in selected),
            encoding="utf-8",
        )

    probes = {
        "schema_version": 1,
        "fixture_revision": fixture_revision,
        "status": "synthetic-categorical-composition-probes",
        "probe_context": "held-out-context",
        "test_context_seed": TEST_CONTEXT,
        "compositions": {},
    }
    test_by_profile = {record["composition_profile"]: record for record in test_records}
    base_by_profile = {
        record["composition_profile"].removesuffix("-base"): record
        for record in test_records
        if record["composition_profile"].endswith("-base")
    }
    for index, (profile, axes) in enumerate(COMPOSITIONS):
        combo = test_by_profile[profile]
        base = base_by_profile[profile]
        combo_tokens = [int(x) for x in combo["tokens"]]
        base_tokens = [int(x) for x in base["tokens"]]
        limit = min(len(base_tokens), len(combo_tokens))
        divergence = next(
            (i for i in range(limit) if base_tokens[i] != combo_tokens[i]),
            None,
        )
        if divergence is None or divergence == 0 or divergence >= limit:
            raise RuntimeError(f"composition pair {profile} lacks a proper shared prefix")
        probes["compositions"][profile] = {
            "index": index,
            "axes": list(axes),
            "low_conditioning": dict(BASE_CONDITIONING),
            "high_conditioning": _conditioning(axes),
            "performance_controls": dict(NEUTRAL_CONTROLS),
            "low_record_source_id": base["source_id"],
            "high_record_source_id": combo["source_id"],
            "prefix_tokens": base_tokens[:divergence],
            "prefix_length": divergence,
            "first_target_divergence_index": divergence,
        }
    (output_dir / "composition-probes.json").write_text(
        json.dumps(probes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    metadata = {
        "schema_version": 1,
        "status": "synthetic-categorical-composition-fixture",
        "fixture_revision": fixture_revision,
        "production_use": False,
        "training_regime": training_profile,
        "composition_profiles": [profile for profile, _ in COMPOSITIONS],
        "sparse_training_compositions": (
            [profile for profile, _ in SPARSE_TRAINING_COMPOSITIONS]
            if training_profile == "sparse-multi-axis"
            else []
        ),
        "pairwise_training_compositions": (
            [profile for profile, _ in PAIRWISE_TRAINING_COMPOSITIONS]
            if training_profile == "pairwise-multi-axis-40"
            else []
        ),
        "matched_single_axis_extra_record_count": (
            len(MATCHED_SINGLE_AXIS_EXTRA_RECORDS)
            if training_profile == "matched-single-axis-32"
            else 0
        ),
        "pairwise_direct_test_overlap_profiles": (
            [
                profile
                for profile, axes in COMPOSITIONS
                if len(axes) == 2
            ]
            if training_profile == "pairwise-multi-axis-40"
            else []
        ),
        "split_counts": counts,
        "test_context_seed": TEST_CONTEXT,
    }
    (output_dir / "fixture-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"record_count": len(records), "split_counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--training-profile",
        choices=("single-axis-only", "matched-single-axis-32", "sparse-multi-axis", "pairwise-multi-axis-40"),
        default="single-axis-only",
    )
    args = parser.parse_args()
    try:
        result = build_fixture(args.output_dir, training_profile=args.training_profile)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1
    print(
        "PASS: categorical composition fixture "
        f"records={result['record_count']} splits={result['split_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
