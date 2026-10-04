#!/usr/bin/env python3
"""Aggregate held-out conditioning probe reports across validation contexts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


TEACHER_METRICS = (
    "target_probability_directional_response_rate",
    "target_family_probability_directional_response_rate",
    "mean_target_probability_delta_native_minus_counterfactual",
    "mean_distribution_total_variation_native_vs_counterfactual",
)
SEQUENCE_METRICS = (
    "controls_with_sequence_change",
    "mean_control_max_total_variation",
    "max_control_max_total_variation",
    "min_control_max_total_variation",
)


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty value set")
    return sum(values) / len(values)


def _sample_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(
        sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    )


def _stats(values: list[float]) -> dict[str, Any]:
    return {
        "mean": _mean(values),
        "sample_stddev": _sample_stddev(values),
        "values": values,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def _summarize_sequence_report(payload: dict[str, Any]) -> dict[str, float]:
    controls = payload.get("controls")
    if not isinstance(controls, dict) or not controls:
        raise ValueError("sequence report controls must be a non-empty object")

    sequence_changed = 0
    max_tvs: list[float] = []
    for control_name, entry in controls.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"sequence report control {control_name!r} must be an object"
            )
        torch_report = entry.get("torch")
        if not isinstance(torch_report, dict):
            raise ValueError(
                f"sequence report control {control_name!r} is missing torch metrics"
            )
        if torch_report.get("sequence_changed") is True:
            sequence_changed += 1
        response = torch_report.get("distribution_response")
        if not isinstance(response, dict):
            raise ValueError(
                f"sequence report control {control_name!r} is missing distribution response"
            )
        max_total_variation = response.get("max_total_variation")
        if not isinstance(max_total_variation, (int, float)):
            raise ValueError(
                f"sequence report control {control_name!r} has no numeric max_total_variation"
            )
        max_tvs.append(float(max_total_variation))

    return {
        "controls_with_sequence_change": float(sequence_changed),
        "mean_control_max_total_variation": _mean(max_tvs),
        "min_control_max_total_variation": min(max_tvs),
        "max_control_max_total_variation": max(max_tvs),
    }


def summarize_heldout_contexts(
    matched_dir: Path,
    diverse_dir: Path,
    *,
    context_count: int = 4,
) -> dict[str, Any]:
    if context_count <= 0:
        raise ValueError("context_count must be positive")

    per_context: list[dict[str, Any]] = []
    for index in range(context_count):
        context_name = f"context-{index:02d}"
        matched_teacher = _load_json(
            matched_dir / f"{context_name}-teacher.json"
        )
        diverse_teacher = _load_json(
            diverse_dir / f"{context_name}-teacher.json"
        )
        matched_sequence = _load_json(
            matched_dir / f"{context_name}-sequence.json"
        )
        diverse_sequence = _load_json(
            diverse_dir / f"{context_name}-sequence.json"
        )

        for label, payload in (
            ("matched teacher", matched_teacher),
            ("diverse teacher", diverse_teacher),
            ("matched sequence", matched_sequence),
            ("diverse sequence", diverse_sequence),
        ):
            if payload.get("status") != "PASS":
                raise ValueError(
                    f"{context_name}: {label} report is not PASS"
                )

        teacher = {
            metric: {
                "matched": float(matched_teacher[metric]),
                "diverse": float(diverse_teacher[metric]),
                "delta": float(diverse_teacher[metric])
                - float(matched_teacher[metric]),
            }
            for metric in TEACHER_METRICS
        }
        matched_sequence_metrics = _summarize_sequence_report(
            matched_sequence
        )
        diverse_sequence_metrics = _summarize_sequence_report(
            diverse_sequence
        )
        sequence = {
            metric: {
                "matched": matched_sequence_metrics[metric],
                "diverse": diverse_sequence_metrics[metric],
                "delta": diverse_sequence_metrics[metric]
                - matched_sequence_metrics[metric],
            }
            for metric in SEQUENCE_METRICS
        }
        per_context.append(
            {
                "context": context_name,
                "teacher_forced": teacher,
                "grammar_constrained_sequence": sequence,
            }
        )

    aggregate: dict[str, Any] = {}
    for section, metrics in (
        ("teacher_forced", TEACHER_METRICS),
        ("grammar_constrained_sequence", SEQUENCE_METRICS),
    ):
        aggregate[section] = {}
        for metric in metrics:
            aggregate[section][metric] = _stats(
                [
                    float(item[section][metric]["delta"])
                    for item in per_context
                ]
            )

    return {
        "schema_version": 1,
        "status": "PASS",
        "context_count": context_count,
        "per_context": per_context,
        "aggregate_diverse_minus_matched": aggregate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matched_dir", type=Path)
    parser.add_argument("diverse_dir", type=Path)
    parser.add_argument("--context-count", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        summary = summarize_heldout_contexts(
            args.matched_dir,
            args.diverse_dir,
            context_count=args.context_count,
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 1

    encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
