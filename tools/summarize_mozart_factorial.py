#!/usr/bin/env python3
"""Summarize the 2x2 target/conditioning diversity factorial experiment."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SEEDS = (7, 42, 123)

FIT_METRICS = {
    "validation_loss": ("fit", "validation_loss_delta"),
    "target_probability_directional_response_rate": (
        "teacher_forced",
        "target_probability_directional_response_rate_delta",
    ),
    "target_family_directional_response_rate": (
        "teacher_forced",
        "target_family_probability_directional_response_rate_delta",
    ),
    "mean_target_probability_delta": (
        "teacher_forced",
        "mean_target_probability_delta_delta",
    ),
    "mean_teacher_forced_tv": (
        "teacher_forced",
        "mean_distribution_total_variation_delta",
    ),
    "controls_with_sequence_change": (
        "grammar_constrained_sequence",
        "controls_with_sequence_change_delta",
    ),
    "mean_control_max_tv": (
        "grammar_constrained_sequence",
        "mean_control_max_total_variation_delta",
    ),
}

HELDOUT_METRICS = {
    "target_probability_directional_response_rate": (
        "teacher_forced",
        "target_probability_directional_response_rate",
        "mean",
    ),
    "target_family_directional_response_rate": (
        "teacher_forced",
        "target_family_probability_directional_response_rate",
        "mean",
    ),
    "mean_target_probability_delta": (
        "teacher_forced",
        "mean_target_probability_delta_native_minus_counterfactual",
        "mean",
    ),
    "mean_distribution_total_variation": (
        "teacher_forced",
        "mean_distribution_total_variation_native_vs_counterfactual",
        "mean",
    ),
    "controls_with_sequence_change": (
        "grammar_constrained_sequence",
        "controls_with_sequence_change",
        "mean",
    ),
    "mean_control_max_total_variation": (
        "grammar_constrained_sequence",
        "mean_control_max_total_variation",
        "mean",
    ),
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_path(payload: dict[str, Any], path: tuple[str, ...]) -> float:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"missing metric path component {key!r}")
        current = current[key]
    if not isinstance(current, (int, float)):
        raise ValueError(f"metric at {path!r} is not numeric")
    return float(current)


def _summarize(values: list[float]) -> dict[str, Any]:
    if len(values) != len(SEEDS):
        raise ValueError("factorial summary requires exactly three seed values")
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return {
        "mean": mean,
        "sample_stddev": math.sqrt(variance),
        "per_seed": dict(zip(SEEDS, values)),
    }


def _factorial_metric(
    summaries: list[dict[str, Any]],
    arm_metric_path: tuple[str, ...],
    *,
    heldout: bool,
) -> dict[str, Any]:
    if heldout:
        target_path = ("heldout_target_only_context_control", "aggregate_diverse_minus_matched") + arm_metric_path
        conditioning_path = ("heldout_conditioning_context_control", "aggregate_diverse_minus_matched") + arm_metric_path
        joint_path = ("heldout_joint_context_control", "aggregate_diverse_minus_matched") + arm_metric_path
    else:
        target_path = ("target_only_context_control", "diverse_minus_matched") + arm_metric_path
        conditioning_path = ("conditioning_context_control", "diverse_minus_matched") + arm_metric_path
        joint_path = ("joint_context_control", "diverse_minus_matched") + arm_metric_path

    target = [_read_path(summary, target_path) for summary in summaries]
    conditioning = [_read_path(summary, conditioning_path) for summary in summaries]
    joint = [_read_path(summary, joint_path) for summary in summaries]
    interaction = [
        both - target_main - conditioning_main
        for both, target_main, conditioning_main in zip(joint, target, conditioning)
    ]
    return {
        "target_main_effect": _summarize(target),
        "conditioning_main_effect": _summarize(conditioning),
        "joint_total_effect": _summarize(joint),
        "target_x_conditioning_interaction": _summarize(interaction),
    }


def summarize_factorial(seed_dir: Path) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for seed in SEEDS:
        path = seed_dir / f"ml-context-diversity-summary-seed-{seed}.json"
        if not path.exists():
            raise ValueError(f"missing required seed summary: {path}")
        payload = _load(path)
        if payload.get("status") != "PASS":
            raise ValueError(f"seed {seed} summary is not PASS")
        for name in (
            "target_only_context_control",
            "conditioning_context_control",
            "joint_context_control",
            "heldout_target_only_context_control",
            "heldout_conditioning_context_control",
            "heldout_joint_context_control",
        ):
            value = payload.get(name)
            if not isinstance(value, dict) or value.get("status") != "PASS":
                raise ValueError(f"seed {seed}: required arm {name} must PASS")
        summaries.append(payload)

    factorial = {
        name: _factorial_metric(summaries, path, heldout=False)
        for name, path in FIT_METRICS.items()
    }
    heldout = {
        name: _factorial_metric(summaries, path, heldout=True)
        for name, path in HELDOUT_METRICS.items()
    }
    return {
        "schema_version": 1,
        "fixture_revision": "mozart-conditioning-fixture-v2",
        "seeds": list(SEEDS),
        "replication_count": len(summaries),
        "status": "PASS",
        "metrics": factorial,
        "heldout_metrics": heldout,
        "definition": {
            "target_main_effect": "target-only minus matched",
            "conditioning_main_effect": "conditioning-only minus matched",
            "joint_total_effect": "joint minus matched",
            "target_x_conditioning_interaction": (
                "joint - target-only - conditioning-only + matched"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = summarize_factorial(args.seed_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
