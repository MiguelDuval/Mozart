#!/usr/bin/env python3
"""Build evaluation-only conditioning probes around unseen validation contexts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_conditioning_fixture_corpus import (
    CONTROL_ORDER,
    FIXTURE_REVISION,
    _longest_common_prefix,
    make_smf,
    render_notes,
)
from midi_to_training_example import build_example
from mozart_conditioning import validate_performance_controls


PROBE_STATUS = "synthetic-conditioning-sequence-probes"
DEFAULT_MAX_CONTEXTS = 4
RENDER_SEED_BASE = 70_000
CONDITIONING_SEED_BASE = 170_000


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: record must be an object")
        records.append(record)
    if not records:
        raise ValueError(f"{path}: no records")
    return records


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _context_conditioning(base: dict[str, Any]) -> dict[str, Any]:
    conditioning = base.get("conditioning")
    if not isinstance(conditioning, dict):
        raise ValueError("validation record is missing conditioning metadata")
    return {
        key: conditioning[key]
        for key in ("style", "substyle", "mood", "rhythm", "role")
    }


def build_heldout_probe_corpus(
    validation_jsonl: Path,
    output_dir: Path,
    *,
    max_contexts: int = DEFAULT_MAX_CONTEXTS,
) -> dict[str, Any]:
    if max_contexts <= 0:
        raise ValueError("max_contexts must be positive")
    validation_records = _load_jsonl(validation_jsonl)
    if len(validation_records) < max_contexts:
        raise ValueError(
            f"expected at least {max_contexts} validation contexts; "
            f"got {len(validation_records)}"
        )
    validation_records = validation_records[:max_contexts]

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            f"output directory must be empty when it exists: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    contexts: list[dict[str, Any]] = []
    for context_index, base_record in enumerate(validation_records):
        if base_record.get("split") != "validation":
            raise ValueError(
                f"validation context {context_index} must have split=validation"
            )

        base_controls = validate_performance_controls(
            base_record.get("performance_controls")
        )
        conditioning = _context_conditioning(base_record)
        context_dir = output_dir / f"context-{context_index:02d}"
        midi_dir = context_dir / "midi"
        midi_dir.mkdir(parents=True, exist_ok=True)

        context_records: list[dict[str, Any]] = []
        probes: dict[str, dict[str, Any]] = {}

        for control_index, name in enumerate(CONTROL_ORDER):
            low_controls = dict(base_controls)
            low_controls[name] = 0.1
            high_controls = dict(base_controls)
            high_controls[name] = 0.9

            render_seed = (
                RENDER_SEED_BASE
                + context_index * 100
                + control_index
            )
            conditioning_seed = (
                CONDITIONING_SEED_BASE
                + context_index * 100
                + control_index
            )

            token_streams: dict[str, list[int]] = {}
            record_ids: dict[str, str] = {}
            for side, controls in (("low", low_controls), ("high", high_controls)):
                filename = f"{name}-{side}.mid"
                midi_path = midi_dir / filename
                midi_path.write_bytes(
                    make_smf(
                        bars=4,
                        beats_per_bar=4,
                        notes_by_bar=render_notes(
                            controls,
                            seed=render_seed,
                        ),
                    )
                )
                source_id = (
                    f"heldout-context-{context_index:02d}-{name}-{side}"
                )
                record = build_example(
                    midi_path,
                    source_id=source_id,
                    source_revision=FIXTURE_REVISION,
                    source_path=f"midi/{filename}",
                    style=conditioning["style"],
                    substyle=conditioning["substyle"],
                    mood=conditioning["mood"],
                    rhythm=conditioning["rhythm"],
                    role=conditioning["role"],
                    seed=conditioning_seed,
                    performance_controls=controls,
                )
                record["split"] = "validation"
                record["target_sha256"] = _sha256(midi_path)
                context_records.append(record)
                token_streams[side] = list(record["tokens"])
                record_ids[side] = source_id

            prefix = _longest_common_prefix(
                token_streams["low"],
                token_streams["high"],
            )
            probes[name] = {
                "low_profile": low_controls,
                "high_profile": high_controls,
                "prefix_tokens": list(prefix),
                "prefix_length": len(prefix),
                "first_target_divergence_index": len(prefix),
                "low_record_source_id": record_ids["low"],
                "high_record_source_id": record_ids["high"],
                "context_source_id": base_record["source_id"],
                "context_index": context_index,
                "control_index": control_index,
                "render_seed": render_seed,
            }

        context_dir.joinpath("records.jsonl").write_text(
            "".join(
                json.dumps(record, sort_keys=True) + "\n"
                for record in context_records
            ),
            encoding="utf-8",
        )
        probe_payload = {
            "schema_version": 1,
            "fixture_revision": FIXTURE_REVISION,
            "status": PROBE_STATUS,
            "probe_context": f"heldout-validation-context-{context_index:02d}",
            "probe_variant": 0,
            "control_probe_values": {
                "low": 0.1,
                "high": 0.9,
                "base_other_controls": None,
            },
            "max_generated_tokens": 32,
            "controls": probes,
        }
        context_dir.joinpath("sequence-probes.json").write_text(
            json.dumps(probe_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        contexts.append(
            {
                "context_index": context_index,
                "validation_source_id": base_record["source_id"],
                "validation_controls": base_controls,
                "record_count": len(context_records),
                "probe_count": len(probes),
                "records_path": (
                    context_dir.relative_to(output_dir) / "records.jsonl"
                ).as_posix(),
                "probe_path": (
                    context_dir.relative_to(output_dir) / "sequence-probes.json"
                ).as_posix(),
            }
        )

    manifest = {
        "schema_version": 1,
        "fixture_revision": FIXTURE_REVISION,
        "status": "synthetic-heldout-conditioning-probe-corpus",
        "source_validation_jsonl": validation_jsonl.as_posix(),
        "context_count": len(contexts),
        "controls_per_context": len(CONTROL_ORDER),
        "record_count": sum(item["record_count"] for item in contexts),
        "probe_count": sum(item["probe_count"] for item in contexts),
        "contexts": contexts,
    }
    output_dir.joinpath("manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation_jsonl", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-contexts", type=int, default=DEFAULT_MAX_CONTEXTS)
    args = parser.parse_args()
    try:
        manifest = build_heldout_probe_corpus(
            args.validation_jsonl,
            args.output_dir,
            max_contexts=args.max_contexts,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "PASS: held-out conditioning probes "
        f"contexts={manifest['context_count']} "
        f"records={manifest['record_count']} "
        f"probes={manifest['probe_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
