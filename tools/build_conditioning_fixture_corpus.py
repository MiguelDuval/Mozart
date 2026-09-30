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
from dataset_split import assign_records
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
)

CONTROL_ORDER = (
    "density",
    "energy",
    "syncopation",
    "swing",
    "variation",
)


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


def build_conditioning_fixture_corpus(output_dir: Path) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            f"output directory must be empty when it exists: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    midi_dir = output_dir / "midi"
    midi_dir.mkdir()

    records: list[dict] = []
    profiles: list[dict] = []

    for index, controls in enumerate(CONTROL_PROFILES):
        filename = f"control-probe-{index:02d}.mid"
        midi_path = midi_dir / filename
        midi_path.write_bytes(
            make_smf(
                bars=4,
                beats_per_bar=4,
                notes_by_bar=render_notes(controls, seed=17 + index),
            )
        )

        record = build_example(
            midi_path,
            source_id=f"mozart-conditioning-source-{index:02d}",
            source_revision=FIXTURE_REVISION,
            source_path=f"midi/{filename}",
            style="electronic",
            substyle="techno",
            mood="driving",
            rhythm="straight",
            role="bass",
            seed=5000 + index,
            performance_controls=controls,
        )
        records.append(record)
        profiles.append(
            {
                "index": index,
                "file": f"midi/{filename}",
                "performance_controls": controls,
                "target_sha256": sha256_file(midi_path),
                "token_count": len(record["tokens"]),
            }
        )

    assigned = assign_records(records)
    records_path = output_dir / "records.jsonl"
    records_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in assigned
        ),
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
    }
    (output_dir / "fixture-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "record_count": len(assigned),
        "output_dir": str(output_dir),
        "profiles": profiles,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    try:
        result = build_conditioning_fixture_corpus(args.output_dir)
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
