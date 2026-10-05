#!/usr/bin/env python3
"""Aggregate three-seed Mozart conditioning dose-response diagnostics."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SEEDS = (7, 42, 123)
METRICS = (
    ("target_response", "slope_around_neutral"),
    ("target_response", "monotonic_nondecreasing_fraction"),
    ("target_response", "integrated_absolute_response"),
    ("distribution_response", "integrated_tv_from_neutral"),
    ("distribution_response", "max_tv_from_neutral"),
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if value.get("schema_version") != 3:
        raise ValueError(f"{path} must have schema_version=3")
    if not isinstance(value.get("source_commit"), str) or not value["source_commit"]:
        raise ValueError(f"{path} must declare source_commit")
    if not isinstance(value.get("fit_contract"), dict):
        raise ValueError(f"{path} must declare fit_contract")
    seed = value.get("seed")
    if not isinstance(seed, int):
        raise ValueError(f"{path} must declare integer seed")
    for arm in ("matched", "diverse"):
        fit = value["fit_contract"].get(arm)
        if not isinstance(fit, dict):
            raise ValueError(f"{path} must declare {arm} fit contract")
        if fit.get("seed") != seed:
            raise ValueError(f"{path} {arm} fit seed must match seed")
        if fit.get("total_optimizer_updates") != 480:
            raise ValueError(f"{path} {arm} fit must contain exactly 480 optimizer updates")
        if fit.get("train_records") != 20 or fit.get("repeat_train_records") != 8:
            raise ValueError(f"{path} {arm} fit train contract mismatch")
        if fit.get("batch_size") != 4 or fit.get("learning_rate") != 3e-4:
            raise ValueError(f"{path} {arm} fit optimization contract mismatch")
        if fit.get("fit_diagnostic") is not True or fit.get("deterministic") is not True:
            raise ValueError(f"{path} {arm} fit must be deterministic fit-diagnostic")
        if fit.get("device") != "cpu":
            raise ValueError(f"{path} {arm} fit device must be cpu")
    if value.get("status") != "PASS":
        raise ValueError(f"{path} must have status=PASS")
    return value


def _stats(values: list[float]) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("dose-response aggregation requires exactly three seeds")
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return {
        "mean": mean,
        "sample_stddev": math.sqrt(variance),
        "per_seed": dict(zip(SEEDS, values)),
    }


def _read_metric(report: dict[str, Any], control: str, group: str, name: str) -> float:
    return float(report["controls"][control][group][name])


def summarize(seed_dir: Path) -> dict[str, Any]:
    payloads = {}
    for seed in SEEDS:
        path = seed_dir / f"dose-response-seed-{seed}.json"
        if not path.exists():
            raise ValueError(f"missing seed report: {path}")
        payloads[seed] = _load(path)

    source_commits = {payloads[seed]["source_commit"] for seed in SEEDS}
    if len(source_commits) != 1:
        raise ValueError("all seed reports must come from the same source commit")
    levels = payloads[7]["levels"]
    for seed in SEEDS:
        if payloads[seed]["levels"] != levels:
            raise ValueError("all seed reports must use identical dose levels")

    output: dict[str, Any] = {
        "schema_version": 3,
        "source_commit": payloads[7]["source_commit"],
        "fit_contract": {
            arm: payloads[7]["fit_contract"][arm]
            for arm in ("matched", "diverse")
        },
        "fixture_revision": "mozart-conditioning-fixture-v2",
        "seeds": list(SEEDS),
        "levels": payloads[7]["levels"],
        "status": "PASS",
        "controls": {},
    }

    for control in ("density", "energy", "syncopation", "swing", "variation"):
        control_out: dict[str, Any] = {}
        for group, metric_name in METRICS:
            key = f"{group}.{metric_name}"
            matched = [
                _read_metric(payloads[seed]["matched"], control, group, metric_name)
                for seed in SEEDS
            ]
            diverse = [
                _read_metric(payloads[seed]["diverse"], control, group, metric_name)
                for seed in SEEDS
            ]
            delta = [b - a for a, b in zip(matched, diverse)]
            control_out[key] = {
                "matched": _stats(matched),
                "diverse": _stats(diverse),
                "diverse_minus_matched": _stats(delta),
            }
        control_out["level_curves"] = {
            "matched": {
                str(seed): payloads[seed]["matched"]["controls"][control]["rows"]
                for seed in SEEDS
            },
            "diverse": {
                str(seed): payloads[seed]["diverse"]["controls"][control]["rows"]
                for seed in SEEDS
            },
        }
        output["controls"][control] = control_out

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = summarize(args.seed_dir)
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
