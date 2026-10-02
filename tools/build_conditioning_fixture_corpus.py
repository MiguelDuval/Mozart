#!/usr/bin/env python3
"""Build a deterministic synthetic corpus whose targets are driven by explicit controls.

This corpus is development-only. Performance controls are declared independently
as intent, then a deterministic musical renderer uses those controls to construct
the target MIDI. Controls are never derived from the target events.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_fixture_corpus import make_smf, sha256_file
from dataset_split import assign_records, split_for_key
from midi_to_training_example import build_example
from mozart_conditioning import PERFORMANCE_CONTROL_NAMES


FIXTURE_REVISION = "mozart-conditioning-fixture-v1"
BASE_PROFILE = {
    "density": 0.5,
    "energy": 0.5,
    "syncopation": 0.5,
    "swing": 0.5,
    "variation": 0.5,
}

CONTROL_PROFILES: tuple[dict[str, float], ...] = tuple(
    [
        {**BASE_PROFILE, name: value}
        for name in PERFORMANCE_CONTROL_NAMES
        for value in (0.1, 0.9)
    ]
    + [
        {
            "density": 0.2,
            "energy": 0.8,
            "syncopation": 0.7,
            "swing": 0.2,
            "variation": 0.8,
        },
        {
            "density": 0.8,
            "energy": 0.2,
            "syncopation": 0.2,
            "swing": 0.8,
            "variation": 0.2,
        },
    ]
)

CONTROL_ORDER = (
    "density",
    "energy",
    "syncopation",
    "swing",
    "variation",
)


def deterministic_source_ids(count: int) -> list[str]:
    """Return exactly count-2 train, 1 validation and 1 test groups."""
    selected: dict[str, list[str]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    for index in range(500_000):
        source_id = f"mozart-conditioning-source-{index:06d}"
        split = split_for_key(f"{source_id}\0{FIXTURE_REVISION}")
        if split == "train" and len(selected["train"]) < count - 2:
            selected["train"].append(source_id)
        elif split in ("validation", "test") and len(selected[split]) < 1:
            selected[split].append(source_id)
        if sum(len(values) for values in selected.values()) >= count:
            break

    result = selected["train"] + selected["validation"] + selected["test"]
    if len(result) != count:
        raise RuntimeError("could not construct deterministic conditioning splits")
    return result


def render_notes(controls: dict[str, float], seed: int) -> list[list[tuple[int, int, int, int]]]:
    """Render four bars from controls chosen independently from the target."""
    notes: list[list[tuple[int, int, int, int]]] = []

    density = controls["density"]
    energy = controls["energy"]
    syncopation = controls["syncopation"]
    swing = controls["swing"]
    variation = controls["variation"]

    notes_per_bar = max(2, min(12, 2 + round(density * 10)))
    base_velocity = max(28, min(124, 36 + round(78 * energy)))

    for bar in range(4):
        bar_notes: list[tuple[int, int, int, int]] = []
        for index in range(notes_per_bar):
            phase = (index * 7 + bar * 5 + seed) % 16
            straight_step = (index * 16) // notes_per_bar
            offbeat_step = min(15, straight_step + 1)
            start_step = (
                offbeat_step
                if ((index + bar + seed) % 10) / 10.0 < syncopation
                else straight_step
            )
            start_step = (start_step + phase) % 16

            pitch_offset = (
                ((index * 3 + bar * 2 + seed) % 7)
                if ((index + seed) % 4) / 4.0 < variation
                else (index + bar) % 3
            )
            note = 36 + pitch_offset

            swing_extra = (
                1
                if swing >= 0.5 and index % 2 == 1
                else 0
            )
            duration_steps = max(
                1,
                min(8, 2 + swing_extra + int(round(variation * 2)) % 2),
            )
            velocity = max(
                1,
                min(
                    127,
                    base_velocity + ((index + bar + seed) % 5 - 2) * 3,
                ),
            )
            max_duration = max(1, 16 - start_step)
            duration_steps = min(duration_steps, max_duration)

            bar_notes.append(
                (
                    note,
                    start_step * 120,
                    duration_steps * 120,
                    velocity,
                )
            )

        bar_notes.sort(key=lambda item: (item[1], item[0], item[2], item[3]))
        notes.append(bar_notes)

    return notes


def _longest_common_prefix(left: list[int], right: list[int]) -> tuple[int, ...]:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    if index == 0:
        raise RuntimeError("control pair has no shared BOS prefix")
    if index >= len(left) or index >= len(right):
        raise RuntimeError("control pair targets are identical")
    return tuple(left[:index])


def _profile_key(controls: dict[str, float]) -> tuple[float, ...]:
    return tuple(float(controls[name]) for name in CONTROL_ORDER)


def _build_sequence_probes(records: list[dict]) -> dict:
    probes: dict[str, dict] = {}
    indexed: dict[tuple[float, ...], list[dict]] = {}
    for record in records:
        indexed.setdefault(
            _profile_key(record["performance_controls"]),
            [],
        ).append(record)

    for name in CONTROL_ORDER:
        low_profile = dict(BASE_PROFILE)
        low_profile[name] = 0.1
        high_profile = dict(BASE_PROFILE)
        high_profile[name] = 0.9
        low_record = next(
            (
                record
                for record in indexed.get(_profile_key(low_profile), [])
                if record.get("split") == "train"
            ),
            None,
        )
        high_record = next(
            (
                record
                for record in indexed.get(_profile_key(high_profile), [])
                if record.get("split") == "train"
            ),
            None,
        )
        if low_record is None or high_record is None:
            raise RuntimeError(
                f"control pair for {name} must contain train records on both sides"
            )

        prefix = _longest_common_prefix(
            list(low_record["tokens"]),
            list(high_record["tokens"]),
        )
        if len(prefix) >= 32:
            raise RuntimeError(
                f"control pair for {name} leaves no generation budget"
            )
        first_divergence = len(prefix)

        probes[name] = {
            "low_profile": low_profile,
            "high_profile": high_profile,
            "prefix_tokens": list(prefix),
            "prefix_length": len(prefix),
            "first_target_divergence_index": first_divergence,
            "low_record_source_id": low_record["source_id"],
            "high_record_source_id": high_record["source_id"],
        }

    return {
        "schema_version": 1,
        "fixture_revision": FIXTURE_REVISION,
        "status": "synthetic-conditioning-sequence-probes",
        "control_probe_values": {
            "low": 0.1,
            "high": 0.9,
            "base_other_controls": 0.5,
        },
        "max_generated_tokens": 32,
        "controls": probes,
    }


def build_conditioning_fixture_corpus(
    output_dir: Path,
    *,
    context_variant_count: int = 0,
) -> dict:
    if context_variant_count < 0 or context_variant_count > len(CONTROL_PROFILES):
        raise ValueError(
            "context_variant_count must be between 0 and the number of control profiles"
        )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            f"output directory must be empty when it exists: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    midi_dir = output_dir / "midi"
    midi_dir.mkdir()

    records: list[dict] = []
    profiles: list[dict] = []
    profile_specs = [
        (index, controls, 0)
        for index, controls in enumerate(CONTROL_PROFILES)
    ]
    profile_specs.extend(
        (index, controls, 1)
        for index, controls in enumerate(
            CONTROL_PROFILES[:context_variant_count]
        )
    )
    # Each base control profile gets one deterministic source group. Variants
    # derive unique record identities from that base group, while explicitly
    # inheriting its split so the 10/1/1 base split is preserved.
    base_source_ids = deterministic_source_ids(len(CONTROL_PROFILES))
    source_ids: list[str] = []

    for profile_index, controls, variant in profile_specs:
        source_id = base_source_ids[profile_index]
        if variant:
            source_id = f"{source_id}-context-v{variant}"
        source_ids.append(source_id)

        filename = f"control-probe-{profile_index:02d}-v{variant}.mid"
        midi_path = midi_dir / filename
        midi_path.write_bytes(
            make_smf(
                bars=4,
                beats_per_bar=4,
                notes_by_bar=render_notes(
                    controls,
                    seed=17 + (variant * 1009) + profile_index,
                ),
            )
        )

        record = build_example(
            midi_path,
            source_id=source_ids[output_index],
            source_revision=FIXTURE_REVISION,
            source_path=f"midi/{filename}",
            style="electronic",
            substyle="techno",
            mood="driving",
            rhythm="straight",
            role="bass",
            seed=5000 + profile_index + (variant * 1000),
            performance_controls=controls,
        )
        records.append(record)
        profiles.append(
            {
                "index": profile_index,
                "variant": variant,
                "render_seed": 17 + (variant * 1009) + profile_index,
                "file": f"midi/{filename}",
                "performance_controls": controls,
                "target_sha256": sha256_file(midi_path),
                "token_count": len(record["tokens"]),
            }
        )

    assigned = assign_records(records)
    base_split_by_profile = {
        profile_index: assigned[index]["split"]
        for index, (profile_index, _, variant) in enumerate(profile_specs)
        if variant == 0
    }
    for index, (profile_index, _, variant) in enumerate(profile_specs):
        if variant == 1:
            assigned[index]["split"] = base_split_by_profile[profile_index]

    records_path = output_dir / "records.jsonl"
    records_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in assigned
        ),
        encoding="utf-8",
    )

    sequence_probes = _build_sequence_probes(assigned)
    (output_dir / "sequence-probes.json").write_text(
        json.dumps(sequence_probes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    metadata = {
        "schema_version": 1,
        "status": "synthetic-conditioning-fixture",
        "fixture_revision": FIXTURE_REVISION,
        "production_use": False,
        "external_data": False,
        "control_order": list(CONTROL_ORDER),
        "records_path": "records.jsonl",
        "profiles": profiles,
        "context_variant_count": context_variant_count,
    }
    (output_dir / "fixture-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "record_count": len(assigned),
        "output_dir": str(output_dir),
        "profiles": profiles,
        "context_variant_count": context_variant_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--context-variant-count",
        type=int,
        default=0,
        help="Add one independent target-MIDI context variant for this many leading control profiles.",
    )
    args = parser.parse_args()

    try:
        result = build_conditioning_fixture_corpus(
            args.output_dir,
            context_variant_count=args.context_variant_count,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "PASS: conditioning fixture corpus "
        f"records={result['record_count']} "
        f"revision={FIXTURE_REVISION}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
