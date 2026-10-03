#!/usr/bin/env python3
"""Build a deterministic fixture for categorical Mozart conditioning diagnostics.

Development-only: each axis changes one categorical conditioning field while
performance controls remain neutral. Train records use multiple contexts and
test pairs use a held-out context.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_fixture_corpus import make_smf, sha256_file
from midi_to_training_example import build_example
from mozart_conditioning import validate_conditioning


FIXTURE_REVISION = "mozart-categorical-conditioning-fixture-v1"
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
CATEGORICAL_PAIRS = {
    "style": ("electronic", "dark_techno"),
    "substyle": ("techno", "dark_techno"),
    "mood": ("neutral", "hypnotic"),
    "rhythm": ("straight", "syncopated"),
    "role": ("bass", "lead"),
}
TRAIN_CONTEXTS = (101, 707)
TEST_CONTEXT = 1901


def _conditioning(axis: str, value: str) -> dict[str, str]:
    if axis not in CATEGORICAL_PAIRS:
        raise ValueError(f"unsupported categorical axis: {axis}")
    result = dict(BASE_CONDITIONING)
    result[axis] = value
    validate_conditioning(**result, seed=0)
    return result


def render_notes(
    conditioning: dict[str, str],
    *,
    context_seed: int,
) -> list[list[tuple[int, int, int, int]]]:
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


def _record(
    output_dir: Path,
    *,
    source_id: str,
    split: str,
    axis: str,
    value: str,
    context_seed: int,
) -> dict:
    conditioning = _conditioning(axis, value)
    filename = f"{axis}-{value.replace('_', '-')}-context-{context_seed}.mid"
    midi_path = output_dir / "midi" / filename
    midi_path.write_bytes(
        make_smf(
            bars=4,
            beats_per_bar=4,
            notes_by_bar=render_notes(
                conditioning,
                context_seed=context_seed,
            ),
        )
    )
    record = build_example(
        midi_path,
        source_id=source_id,
        source_revision=FIXTURE_REVISION,
        source_path=f"midi/{filename}",
        **conditioning,
        seed=50000 + context_seed,
        performance_controls=NEUTRAL_CONTROLS,
    )
    record["split"] = split
    record["target_sha256"] = sha256_file(midi_path)
    record["categorical_axis"] = axis
    record["categorical_value"] = value
    record["context_seed"] = context_seed
    return record


def _longest_common_prefix(left: list[int], right: list[int]) -> tuple[int, ...]:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    if index == 0 or index >= limit:
        raise RuntimeError("categorical pair must have a non-empty proper shared prefix")
    return tuple(left[:index])


def _build_probes(records: list[dict]) -> dict:
    by_key = {
        (r["categorical_axis"], r["categorical_value"]): r
        for r in records
        if r["split"] == "test"
    }
    probes = {}
    for axis, (low, high) in CATEGORICAL_PAIRS.items():
        low_record = by_key[(axis, low)]
        high_record = by_key[(axis, high)]
        prefix = _longest_common_prefix(low_record["tokens"], high_record["tokens"])
        probes[axis] = {
            "conditioning_axis": axis,
            "low_conditioning": _conditioning(axis, low),
            "high_conditioning": _conditioning(axis, high),
            "performance_controls": dict(NEUTRAL_CONTROLS),
            "low_record_source_id": low_record["source_id"],
            "high_record_source_id": high_record["source_id"],
            "prefix_tokens": list(prefix),
            "prefix_length": len(prefix),
            "first_target_divergence_index": len(prefix),
        }
    return {
        "schema_version": 1,
        "fixture_revision": FIXTURE_REVISION,
        "status": "synthetic-categorical-conditioning-probes",
        "probe_context": "held-out-context",
        "test_context_seed": TEST_CONTEXT,
        "control_pairs": {
            axis: {"low": pair[0], "high": pair[1]}
            for axis, pair in CATEGORICAL_PAIRS.items()
        },
        "probes": probes,
    }


def build_fixture(output_dir: Path) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "midi").mkdir()

    records: list[dict] = []
    for axis, (low, high) in CATEGORICAL_PAIRS.items():
        axis_slug = axis.replace("_", "-")
        for value in (low, high):
            value_slug = value.replace("_", "-")
            for context_seed in TRAIN_CONTEXTS:
                records.append(
                    _record(
                        output_dir,
                        source_id=f"categorical-{axis_slug}-{value_slug}-train-{context_seed}",
                        split="train",
                        axis=axis,
                        value=value,
                        context_seed=context_seed,
                    )
                )
            records.append(
                _record(
                    output_dir,
                    source_id=f"categorical-{axis_slug}-{value_slug}-test",
                    split="test",
                    axis=axis,
                    value=value,
                    context_seed=TEST_CONTEXT,
                )
            )

    for index, (axis, value) in enumerate((("style", "dark_techno"), ("role", "lead"))):
        records.append(
            _record(
                output_dir,
                source_id=f"categorical-validation-{index}",
                split="validation",
                axis=axis,
                value=value,
                context_seed=3001 + index,
            )
        )

    counts = {
        split: sum(record["split"] == split for record in records)
        for split in ("train", "validation", "test")
    }
    if len(records) != 32 or counts != {"train": 20, "validation": 2, "test": 10}:
        raise RuntimeError(f"unexpected categorical fixture shape: records={len(records)} splits={counts}")

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

    (output_dir / "sequence-probes.json").write_text(
        json.dumps(_build_probes(records), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metadata = {
        "schema_version": 1,
        "status": "synthetic-categorical-conditioning-fixture",
        "fixture_revision": FIXTURE_REVISION,
        "production_use": False,
        "control_axes": list(CATEGORICAL_PAIRS),
        "train_context_seeds": list(TRAIN_CONTEXTS),
        "test_context_seed": TEST_CONTEXT,
        "split_counts": counts,
    }
    (output_dir / "fixture-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"record_count": len(records), "split_counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    try:
        result = build_fixture(args.output_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1
    print(
        "PASS: categorical conditioning fixture "
        f"records={result['record_count']} splits={result['split_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
