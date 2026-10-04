#!/usr/bin/env python3
"""Measure multi-level teacher-forced conditioning dose-response curves.

The probe fixture supplies paired low/high targets that share the same prefix.
For each control and dose level, this tool evaluates both targets under the same
context. A positive contrast means the high-control target receives more legal
probability mass than the low-control target.

This is a research diagnostic only; it does not alter model architecture or ABI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from evaluate_mozart_conditioning import (
    PERFORMANCE_CONTROL_NAMES,
    _load_onnx_session,
    load_model,
)
from evaluate_mozart_conditioning_sequence import (
    _grammar_allowed_mask,
    _onnx_next_logits,
    _token_distribution_total_variation,
    _torch_next_logits,
    load_sequence_probe_file,
)
from mozart_conditioning import validate_performance_controls


DEFAULT_LEVELS = (0.1, 0.3, 0.5, 0.7, 0.9)
PARITY_TOLERANCE = 1.0e-4


def _parse_levels(value: str) -> tuple[float, ...]:
    try:
        levels = tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("levels must be a comma-separated numeric list") from exc
    if len(levels) < 3:
        raise ValueError("at least three dose levels are required")
    if any(not 0.0 <= level <= 1.0 for level in levels):
        raise ValueError("dose levels must be in [0, 1]")
    if tuple(sorted(levels)) != levels or len(set(levels)) != len(levels):
        raise ValueError("dose levels must be strictly increasing")
    if 0.5 not in levels:
        raise ValueError("dose levels must include neutral value 0.5")
    return levels


def _trapz_mean_absolute(values: list[float], levels: tuple[float, ...]) -> float:
    if len(values) != len(levels):
        raise ValueError("values/levels length mismatch")
    area = 0.0
    for left, right, x0, x1 in zip(values, values[1:], levels, levels[1:]):
        area += 0.5 * (left + right) * (x1 - x0)
    span = levels[-1] - levels[0]
    return area / span


def _slope_around_neutral(values: dict[float, float], levels: tuple[float, ...]) -> float:
    lower = max(level for level in levels if level < 0.5)
    upper = min(level for level in levels if level > 0.5)
    return (values[upper] - values[lower]) / (upper - lower)


def _monotonic_fraction(values: list[float], *, nondecreasing: bool) -> float:
    if len(values) < 2:
        return 1.0
    correct = 0
    for left, right in zip(values, values[1:]):
        correct += int(right >= left if nondecreasing else right <= left)
    return correct / (len(values) - 1)


def _family_probability(
    logits: np.ndarray,
    target: int,
    context: list[int],
) -> float:
    allowed = _grammar_allowed_mask(context)
    if not allowed[target]:
        raise ValueError(
            f"target token {target} is illegal after the declared teacher-forced context"
        )
    selected = logits[allowed].astype(np.float64, copy=False)
    shifted = selected - np.max(selected)
    probability = np.exp(shifted)
    probability /= np.sum(probability)
    allowed_indices = np.flatnonzero(allowed)

    def family(token: int) -> str:
        if 16 <= token < 32:
            return "channel"
        if 32 <= token < 160:
            return "note"
        if 160 <= token < 192:
            return "velocity"
        if 192 <= token < 256:
            return "time_shift"
        if 256 <= token < 352:
            return "duration"
        if 352 <= token < 480:
            return "controller"
        if 480 <= token < 512:
            return "control_value"
        if token == 2:
            return "eos"
        return "special"

    target_family = family(target)
    return float(
        sum(
            probability[position]
            for position, token in enumerate(allowed_indices)
            if family(int(token)) == target_family
        )
    )


def _target_probability(logits: np.ndarray, target: int, context: list[int]) -> float:
    allowed = _grammar_allowed_mask(context)
    if not allowed[target]:
        raise ValueError(
            f"target token {target} is illegal after the declared teacher-forced context"
        )
    selected = logits[allowed].astype(np.float64, copy=False)
    shifted = selected - np.max(selected)
    probability = np.exp(shifted)
    probability /= np.sum(probability)
    allowed_indices = np.flatnonzero(allowed)
    target_position = int(np.searchsorted(allowed_indices, target))
    return float(probability[target_position])


def evaluate_dose_response(
    model: Any,
    probes: dict[str, Any],
    *,
    levels: tuple[float, ...] = DEFAULT_LEVELS,
    onnx_session: Any | None = None,
) -> dict[str, Any]:
    controls = probes.get("controls")
    if not isinstance(controls, dict):
        raise ValueError("probe file controls must be an object")

    results: dict[str, Any] = {}
    failures: list[str] = []
    for name in PERFORMANCE_CONTROL_NAMES:
        probe = controls.get(name)
        if not isinstance(probe, dict):
            raise ValueError(f"missing probe for control {name}")

        prefix = [int(token) for token in probe["prefix_tokens"]]
        grammar = _grammar_allowed_mask(prefix)
        if not grammar.any():
            raise ValueError(f"probe {name} has no legal continuation")
        low_target = int(probe["low_target_token"])
        high_target = int(probe["high_target_token"])
        if low_target == high_target:
            raise ValueError(f"probe {name} low/high targets must differ")
        if not grammar[low_target] or not grammar[high_target]:
            raise ValueError(
                f"probe {name} low/high targets must both be legal after the shared prefix"
            )

        base_controls = validate_performance_controls(probe["base_profile"])
        level_rows: list[dict[str, Any]] = []
        target_contrasts: list[float] = []
        family_contrasts: list[float] = []
        tv_from_neutral: list[float] = []
        torch_by_level: dict[float, tuple[np.ndarray, np.ndarray]] = {}

        for level in levels:
            controls_at_level = dict(base_controls)
            controls_at_level[name] = level
            logits = _torch_next_logits(model, prefix, controls_at_level)
            low_probability = _target_probability(logits, low_target, prefix)
            high_probability = _target_probability(logits, high_target, prefix)
            low_family_probability = _family_probability(logits, low_target, prefix)
            high_family_probability = _family_probability(logits, high_target, prefix)
            torch_by_level[level] = (logits, np.asarray([low_probability, high_probability]))

            level_rows.append(
                {
                    "level": level,
                    "target_probability_low": low_probability,
                    "target_probability_high": high_probability,
                    "target_probability_contrast_high_minus_low": (
                        high_probability - low_probability
                    ),
                    "target_family_probability_low": low_family_probability,
                    "target_family_probability_high": high_family_probability,
                    "target_family_probability_contrast_high_minus_low": (
                        high_family_probability - low_family_probability
                    ),
                }
            )
            target_contrasts.append(high_probability - low_probability)
            family_contrasts.append(high_family_probability - low_family_probability)

        neutral_logits = torch_by_level[0.5][0]
        for level, (logits, _) in torch_by_level.items():
            tv_from_neutral.append(
                _token_distribution_total_variation(
                    logits,
                    neutral_logits,
                    prefix,
                    grammar_constrained=True,
                )
            )

        target_curve = dict(zip(levels, target_contrasts))
        family_curve = dict(zip(levels, family_contrasts))
        neutral_target = target_curve[0.5]
        neutral_family = family_curve[0.5]
        abs_target = [abs(value - neutral_target) for value in target_contrasts]
        abs_family = [abs(value - neutral_family) for value in family_contrasts]

        entry: dict[str, Any] = {
            "prefix_tokens": prefix,
            "low_target_token": low_target,
            "high_target_token": high_target,
            "levels": list(levels),
            "rows": level_rows,
            "target_response": {
                "neutral_contrast": neutral_target,
                "slope_around_neutral": _slope_around_neutral(target_curve, levels),
                "monotonic_nondecreasing_fraction": _monotonic_fraction(
                    target_contrasts,
                    nondecreasing=True,
                ),
                "integrated_absolute_response": _trapz_mean_absolute(
                    abs_target,
                    levels,
                ),
            },
            "target_family_response": {
                "neutral_contrast": neutral_family,
                "slope_around_neutral": _slope_around_neutral(family_curve, levels),
                "monotonic_nondecreasing_fraction": _monotonic_fraction(
                    family_contrasts,
                    nondecreasing=True,
                ),
                "integrated_absolute_response": _trapz_mean_absolute(
                    abs_family,
                    levels,
                ),
            },
            "distribution_response": {
                "tv_from_neutral_by_level": dict(
                    zip((str(level) for level in levels), tv_from_neutral)
                ),
                "integrated_tv_from_neutral": _trapz_mean_absolute(
                    tv_from_neutral,
                    levels,
                ),
                "max_tv_from_neutral": max(tv_from_neutral),
            },
        }

        if onnx_session is not None:
            onnx_rows: list[dict[str, Any]] = []
            for row in level_rows:
                level = float(row["level"])
                controls_at_level = dict(base_controls)
                controls_at_level[name] = level
                logits = _onnx_next_logits(onnx_session, prefix, controls_at_level)
                low_probability = _target_probability(logits, low_target, prefix)
                high_probability = _target_probability(logits, high_target, prefix)
                onnx_rows.append(
                    {
                        "level": level,
                        "target_probability_low": low_probability,
                        "target_probability_high": high_probability,
                        "target_family_probability_low": _family_probability(
                            logits,
                            low_target,
                            prefix,
                        ),
                        "target_family_probability_high": _family_probability(
                            logits,
                            high_target,
                            prefix,
                        ),
                    }
                )
                if (
                    abs(low_probability - row["target_probability_low"]) > PARITY_TOLERANCE
                    or abs(high_probability - row["target_probability_high"]) > PARITY_TOLERANCE
                ):
                    failures.append(
                        f"PyTorch/ONNX target probability mismatch for control {name} level {level}"
                    )
            entry["onnx_rows"] = onnx_rows

            torch_neutral = torch_by_level[0.5][0]
            onnx_neutral = _onnx_next_logits(
                onnx_session,
                prefix,
                dict(base_controls),
            )
            for level in levels:
                controls_at_level = dict(base_controls)
                controls_at_level[name] = level
                torch_logits = torch_by_level[level][0]
                onnx_logits = _onnx_next_logits(
                    onnx_session,
                    prefix,
                    controls_at_level,
                )
                torch_tv = _token_distribution_total_variation(
                    torch_logits,
                    torch_neutral,
                    prefix,
                    grammar_constrained=True,
                )
                onnx_tv = _token_distribution_total_variation(
                    onnx_logits,
                    onnx_neutral,
                    prefix,
                    grammar_constrained=True,
                )
                if abs(torch_tv - onnx_tv) > PARITY_TOLERANCE:
                    failures.append(
                        f"PyTorch/ONNX TV mismatch for control {name} level {level}"
                    )

        results[name] = entry

    return {
        "status": "FAIL" if failures else "PASS",
        "levels": list(levels),
        "controls": results,
        "failures": failures,
    }


def _load_records(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{path}:{line_number}: missing source_id")
        if source_id in records:
            raise ValueError(f"{path}:{line_number}: duplicate source_id {source_id!r}")
        tokens = record.get("tokens")
        if not isinstance(tokens, list) or len(tokens) < 2:
            raise ValueError(f"{path}:{line_number}: tokens must contain at least two ids")
        records[source_id] = record
    if not records:
        raise ValueError(f"{path}: no records")
    return records


def _load_probe_file(
    path: Path,
    records_path: Path,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("sequence probe file root must be an object")
    if payload.get("status") != "synthetic-conditioning-sequence-probes":
        raise ValueError("unsupported sequence probe file status")
    controls = payload.get("controls")
    if not isinstance(controls, dict):
        raise ValueError("sequence probe file controls must be an object")

    records = _load_records(records_path)
    for name in PERFORMANCE_CONTROL_NAMES:
        probe = controls.get(name)
        if not isinstance(probe, dict):
            raise ValueError(f"missing sequence probe for control {name}")
        low_source = probe.get("low_record_source_id")
        high_source = probe.get("high_record_source_id")
        if not isinstance(low_source, str) or not isinstance(high_source, str):
            raise ValueError(f"probe {name} must declare low/high record source ids")
        low_record = records.get(low_source)
        high_record = records.get(high_source)
        if low_record is None or high_record is None:
            raise ValueError(f"probe {name} references a missing record")
        prefix = probe.get("prefix_tokens")
        if not isinstance(prefix, list) or not prefix:
            raise ValueError(f"probe {name} must contain prefix_tokens")
        if low_record["tokens"][:len(prefix)] != prefix:
            raise ValueError(f"probe {name} low record does not contain declared prefix")
        if high_record["tokens"][:len(prefix)] != prefix:
            raise ValueError(f"probe {name} high record does not contain declared prefix")
        if len(low_record["tokens"]) <= len(prefix) or len(high_record["tokens"]) <= len(prefix):
            raise ValueError(f"probe {name} has no divergence target")
        probe["low_target_token"] = int(low_record["tokens"][len(prefix)])
        probe["high_target_token"] = int(high_record["tokens"][len(prefix)])
        if probe["low_target_token"] == probe["high_target_token"]:
            raise ValueError(f"probe {name} low/high target tokens do not diverge")
        # The two stored profiles differ only in this control; all other controls
        # define the fixed baseline used for every intermediate dose.
        low_profile = dict(probe.get("low_profile", {}))
        high_profile = dict(probe.get("high_profile", {}))
        if set(low_profile) != set(PERFORMANCE_CONTROL_NAMES) or set(high_profile) != set(PERFORMANCE_CONTROL_NAMES):
            raise ValueError(f"probe {name} must expose complete low/high control profiles")
        for other in PERFORMANCE_CONTROL_NAMES:
            if other != name and low_profile[other] != high_profile[other]:
                raise ValueError(f"probe {name} changes more than one performance control")
        base_profile = dict(low_profile)
        base_profile[name] = 0.5
        probe["base_profile"] = base_profile
    return payload

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--onnx", type=Path)
    parser.add_argument("--probe-file", type=Path, required=True)
    parser.add_argument("--records-file", type=Path, required=True)
    parser.add_argument("--levels", type=str, default=",".join(str(x) for x in DEFAULT_LEVELS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    levels = _parse_levels(args.levels)
    model, _ = load_model(args.checkpoint, expected_config_path=args.config)
    onnx_session = _load_onnx_session(args.onnx) if args.onnx is not None else None
    report = evaluate_dose_response(
        model,
        _load_probe_file(args.probe_file, args.records_file),
        levels=levels,
        onnx_session=onnx_session,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
