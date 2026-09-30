#!/usr/bin/env python3
"""Build a deterministic, synthetic end-to-end Mozart fixture corpus.

The generated MIDI is original test material created by this tool. It is
development-only and must never be treated as an audited production source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_training_shards import _stats, write_shards
from build_training_windows import build_windows
from dataset_quality import build_report
from dataset_split import assign_records
from dataset_split import split_for_key
from midi_to_training_example import build_example


PPQ = 480
SPLIT_ORDER = ("train", "validation", "test")
FIXTURE_REVISION = "mozart-synthetic-fixture-v1"


def vlq(value: int) -> bytes:
    if value < 0:
        raise ValueError("VLQ value must be non-negative")
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.reverse()
    return bytes(parts)


def make_smf(
    *,
    bars: int,
    beats_per_bar: int,
    notes_by_bar: list[list[tuple[int, int, int, int]]],
    tempo_bpm: int = 120,
) -> bytes:
    if bars <= 0 or beats_per_bar <= 0:
        raise ValueError("fixture dimensions must be positive")
    if len(notes_by_bar) != bars:
        raise ValueError("notes_by_bar length must equal bars")
    if tempo_bpm <= 0:
        raise ValueError("tempo must be positive")

    denominator_power = 2  # quarter-note denominator
    events = bytearray()
    tempo_us = 60000000 // tempo_bpm
    events += bytes.fromhex("00 FF 51 03") + tempo_us.to_bytes(3, "big")
    events += bytes.fromhex(
        f"00 FF 58 04 {beats_per_bar:02X} {denominator_power:02X} 18 08"
    )

    absolute_events: list[tuple[int, int, bytes]] = []
    ticks_per_bar = beats_per_bar * PPQ
    for bar_index, bar_notes in enumerate(notes_by_bar):
        bar_origin = bar_index * ticks_per_bar
        for note, start_tick, duration_tick, velocity in bar_notes:
            if not 0 <= note <= 127:
                raise ValueError("fixture note out of range")
            if not 0 <= velocity <= 127:
                raise ValueError("fixture velocity out of range")
            if start_tick < 0 or duration_tick <= 0:
                raise ValueError("fixture note timing must be positive")
            if start_tick + duration_tick > ticks_per_bar:
                raise ValueError("fixture note exceeds bar boundary")
            absolute_events.append(
                (bar_origin + start_tick, 1, bytes((0x90, note, velocity)))
            )
            absolute_events.append(
                (
                    bar_origin + start_tick + duration_tick,
                    0,
                    bytes((0x80, note, 0)),
                )
            )

    absolute_events.sort(key=lambda item: (item[0], item[1], item[2]))
    previous_tick = 0
    for tick, _, message in absolute_events:
        events += vlq(tick - previous_tick) + message
        previous_tick = tick
    events += bytes.fromhex("00 FF 2F 00")

    header = b"MThd" + bytes.fromhex("00 00 00 06 00 00 00 01 01 E0")
    track = b"MTrk" + len(events).to_bytes(4, "big") + bytes(events)
    return header + track


def fixture_notes(
    kind: str,
) -> tuple[int, int, list[list[tuple[int, int, int, int]]]]:
    if kind == "bass-4bar":
        bars, meter = 4, 4
        roots = (36, 38, 41, 43)
        notes = [
            [(roots[bar], beat * PPQ, 360, 92) for beat in range(4)]
            for bar in range(bars)
        ]
        return bars, meter, notes

    if kind == "chords-8bar":
        bars, meter = 8, 4
        roots = (48, 50, 53, 55, 48, 50, 55, 53)
        notes = []
        for bar in range(bars):
            root = roots[bar]
            notes.append(
                [
                    (root, 0, 1440, 88),
                    (root + 3, 0, 1440, 82),
                    (root + 7, 0, 1440, 78),
                ]
            )
        return bars, meter, notes

    if kind == "lead-16bar-3-4":
        bars, meter = 16, 3
        scale = (60, 62, 63, 65, 67, 68, 70)
        notes = [
            [
                (scale[(bar + beat) % len(scale)], beat * PPQ, 360, 80 + beat * 6)
                for beat in range(3)
            ]
            for bar in range(bars)
        ]
        return bars, meter, notes

    if kind == "window-20bar":
        bars, meter = 20, 4
        notes = [
            [(40 + (bar % 8), 0, 1920, 72 + (bar % 4) * 8)]
            for bar in range(bars)
        ]
        return bars, meter, notes

    raise ValueError(f"unknown fixture kind: {kind}")


FIXTURES = (
    (
        "bass-4bar",
        "bass-4bar.mid",
        "electronic",
        "techno",
        "driving",
        "straight",
        "bass",
    ),
    (
        "chords-8bar",
        "chords-8bar.mid",
        "electronic",
        "techno",
        "hypnotic",
        "straight",
        "chords",
    ),
    (
        "lead-16bar-3-4",
        "lead-16bar-3-4.mid",
        "electronic",
        "techno",
        "atmospheric",
        "syncopated",
        "lead",
    ),
    (
        "window-20bar",
        "window-20bar.mid",
        "techno",
        "dark_techno",
        "dark",
        "straight",
        "bass",
    ),
)


def source_ids_for_splits() -> dict[str, str]:
    found: dict[str, str] = {}
    for index in range(100_000):
        source_id = f"mozart-fixture-source-{index:05d}"
        split = split_for_key(f"{source_id}\0{FIXTURE_REVISION}")
        found.setdefault(split, source_id)
        if len(found) == len(SPLIT_ORDER):
            break
    if len(found) != len(SPLIT_ORDER):
        raise RuntimeError("could not find deterministic fixture sources for all splits")

    used = set(found.values())
    for index in range(100_000, 200_000):
        source_id = f"mozart-fixture-source-{index:05d}"
        if source_id in used:
            continue
        if split_for_key(f"{source_id}\0{FIXTURE_REVISION}") == "train":
            found["extra_train"] = source_id
            break
    if "extra_train" not in found:
        raise RuntimeError("could not find deterministic extra train fixture source")
    return found


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_hashes(root: Path, *, exclude: set[str] | None = None) -> list[dict]:
    excluded = exclude or set()
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        entries.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def build_fixture_corpus(output_dir: Path) -> dict:
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise ValueError(
                f"output directory must be empty when it exists: {output_dir}"
            )
    else:
        output_dir.mkdir(parents=True)

    midi_dir = output_dir / "midi"
    midi_dir.mkdir()
    records: list[dict] = []
    split_sources = source_ids_for_splits()

    for index, (
        kind,
        filename,
        style,
        substyle,
        mood,
        rhythm,
        role,
    ) in enumerate(FIXTURES):
        bars, meter, notes = fixture_notes(kind)
        midi_path = midi_dir / filename
        midi_path.write_bytes(
            make_smf(bars=bars, beats_per_bar=meter, notes_by_bar=notes)
        )

        source_id = (
            split_sources[SPLIT_ORDER[index]]
            if index < 3
            else split_sources["extra_train"]
        )

        if bars > 16:
            records.extend(
                build_windows(
                    midi_path,
                    source_id=source_id,
                    source_revision=FIXTURE_REVISION,
                    source_path=f"midi/{filename}",
                    style=style,
                    substyle=substyle,
                    mood=mood,
                    rhythm=rhythm,
                    role=role,
                    seed=1000 + index,
                )
            )
        else:
            records.append(
                build_example(
                    midi_path,
                    source_id=source_id,
                    source_revision=FIXTURE_REVISION,
                    source_path=f"midi/{filename}",
                    style=style,
                    substyle=substyle,
                    mood=mood,
                    rhythm=rhythm,
                    role=role,
                    seed=1000 + index,
                )
            )

    assigned = assign_records(records)

    records_path = output_dir / "records.jsonl"
    records_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in assigned
        ),
        encoding="utf-8",
    )

    shards_dir = output_dir / "shards"
    shard_paths = write_shards(
        assigned,
        shards_dir,
        max_records_per_shard=2,
    )

    stats_path = shards_dir / "dataset-statistics.json"
    stats_path.write_text(
        json.dumps(
            _stats(assigned, manifest_sha256=None),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    qa = build_report(assigned, manifest_sha256=None)
    qa_path = output_dir / "qa.json"
    qa_path.write_text(
        json.dumps(qa, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    metadata = {
        "schema_version": 1,
        "status": "synthetic-fixture",
        "fixture_revision": FIXTURE_REVISION,
        "generator": "tools/build_fixture_corpus.py",
        "production_use": False,
        "external_data": False,
        "source_groups": [
            {
                "source_id": source_id,
                "revision": FIXTURE_REVISION,
                "split": split_for_key(f"{source_id}\0{FIXTURE_REVISION}"),
            }
            for source_id in sorted(set(record["source_id"] for record in assigned))
        ],
        "records_path": "records.jsonl",
        "qa_path": "qa.json",
        "statistics_path": "shards/dataset-statistics.json",
        "shard_count": len(shard_paths),
        "files": [],
    }
    metadata_path = output_dir / "fixture-metadata.json"
    metadata["files"] = collect_hashes(
        output_dir,
        exclude={metadata_path.relative_to(output_dir).as_posix()},
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if qa["rejected_count"] != 0:
        raise ValueError("fixture corpus must produce zero rejected records")
    if qa["source_groups_crossing_splits"]:
        raise ValueError("fixture corpus source groups crossed split boundaries")
    if not stats_path.is_file():
        raise ValueError("training statistics file was not generated")

    return {
        "record_count": len(assigned),
        "shard_count": len(shard_paths),
        "split_counts": qa["split_counts"],
        "qa": qa,
        "output_dir": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    try:
        result = build_fixture_corpus(args.output_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "PASS: fixture corpus "
        f"records={result['record_count']} "
        f"shards={result['shard_count']} "
        f"train={result['split_counts']['train']} "
        f"validation={result['split_counts']['validation']} "
        f"test={result['split_counts']['test']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
