#!/usr/bin/env python3
"""Measure teacher-forced target-token responsiveness on the synthetic fixture."""

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
    validate_mozart_token_sequence,
)
from mozart_token_grammar import (
    CHANNEL_BASE,
    CONTROL_VALUE_BASE,
    CONTROLLER_BASE,
    DURATION_BASE,
    EOS,
    NOTE_BASE,
    TIME_SHIFT_BASE,
    VELOCITY_BASE,
)


def _load_records(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(
                f"{path}:{line_number}: missing source_id"
            )
        if source_id in records:
            raise ValueError(
                f"{path}:{line_number}: duplicate source_id {source_id!r}"
            )
        tokens = record.get("tokens")
        if not isinstance(tokens, list) or len(tokens) < 2:
            raise ValueError(
                f"{path}:{line_number}: tokens must contain at least 2 ids"
            )
        controls = record.get("performance_controls")
        if not isinstance(controls, dict):
            raise ValueError(
                f"{path}:{line_number}: missing performance_controls"
            )
        records[source_id] = record

    if not records:
        raise ValueError(f"{path}: no records")
    return records


def _target_rank(logits: np.ndarray, target: int) -> int:
    if logits.shape != (512,):
        raise ValueError("logits must have shape [512]")
    if not 0 <= target < 512:
        raise ValueError(
            "target token must be inside the Mozart vocabulary"
        )
    return 1 + int(np.count_nonzero(logits > logits[target]))


def _legal_target_probability(
    logits: np.ndarray,
    target: int,
    context: list[int],
) -> float:
    allowed = _grammar_allowed_mask(context)
    if not allowed[target]:
        raise ValueError(
            f"target token {target} is not legal after the teacher-forced context"
        )
    selected = logits[allowed].astype(np.float64, copy=False)
    shifted = selected - np.max(selected)
    probabilities = np.exp(shifted)
    probabilities /= np.sum(probabilities)
    allowed_indices = np.flatnonzero(allowed)
    target_position = int(np.searchsorted(allowed_indices, target))
    return float(probabilities[target_position])

def _token_family(target: int) -> str:
    if CHANNEL_BASE <= target < NOTE_BASE:
        return "channel"
    if NOTE_BASE <= target < VELOCITY_BASE:
        return "note"
    if VELOCITY_BASE <= target < TIME_SHIFT_BASE:
        return "velocity"
    if TIME_SHIFT_BASE <= target < DURATION_BASE:
        return "time_shift"
    if DURATION_BASE <= target < CONTROLLER_BASE:
        return "duration"
    if CONTROLLER_BASE <= target < CONTROL_VALUE_BASE:
        return "controller"
    if CONTROL_VALUE_BASE <= target < 512:
        return "control_value"
    if target == EOS:
        return "eos"
    return "special"


def _legal_token_family_probability(
    logits: np.ndarray,
    target: int,
    context: list[int],
) -> float:
    allowed = _grammar_allowed_mask(context)
    if not allowed[target]:
        raise ValueError(
            f"target token {target} is not legal after the teacher-forced context"
        )
    family = _token_family(target)
    family_mask = allowed.copy()
    for token in np.flatnonzero(allowed):
        family_mask[token] = _token_family(int(token)) == family
    selected = logits[allowed].astype(np.float64, copy=False)
    shifted = selected - np.max(selected)
    probabilities = np.exp(shifted)
    probabilities /= np.sum(probabilities)
    allowed_indices = np.flatnonzero(allowed)
    family_positions = np.flatnonzero(
        family_mask[allowed_indices]
    )
    return float(probabilities[family_positions].sum())


def _measure(
    logits: np.ndarray,
    target: int,
    *,
    context: list[int] | None = None,
) -> dict[str, Any]:
    if not np.isfinite(logits).all():
        raise ValueError("logits contain non-finite values")
    rank = _target_rank(logits, target)
    top1 = int(np.argmax(logits))
    target_logit = float(logits[target])
    top1_logit = float(logits[top1])
    report: dict[str, Any] = {
        "target_token": target,
        "target_rank": rank,
        "target_top1": top1 == target,
        "target_logit": target_logit,
        "top1_token": top1,
        "top1_logit": top1_logit,
        "target_top1_margin": target_logit - top1_logit,
    }
    if context is not None:
        allowed = _grammar_allowed_mask(context)
        legal_logits = np.where(allowed, logits, -np.inf)
        legal_target_rank = 1 + int(
            np.count_nonzero(
                legal_logits > legal_logits[target]
            )
        )
        report["target_legal_rank"] = legal_target_rank
        report["target_legal_top1"] = (
            int(np.argmax(legal_logits)) == target
        )
        report["target_probability"] = _legal_target_probability(
            logits,
            target,
            context,
        )
        report["target_token_family"] = _token_family(target)
        report["target_family_probability"] = _legal_token_family_probability(
            logits,
            target,
            context,
        )
    return report


def _evaluate_with_model(
    model: Any,
    records: dict[str, dict[str, Any]],
    probes: dict[str, Any],
    *,
    onnx_session: Any | None = None,
    window_size: int = 8,
    require_target_top1: bool = False,
    require_legal_target_top1: bool = False,
    probe_split: str = "train",
) -> dict[str, Any]:
    controls = probes.get("controls")
    if not isinstance(controls, dict):
        raise ValueError("probe file controls must be an object")
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    if probe_split not in {"train", "validation", "test"}:
        raise ValueError("probe_split must be one of: train, validation, test")

    failures: list[str] = []
    report_controls: dict[str, Any] = {}

    for name in PERFORMANCE_CONTROL_NAMES:
        probe = controls.get(name)
        if not isinstance(probe, dict):
            raise ValueError(f"missing probe for control {name}")

        low_source = probe.get("low_record_source_id")
        high_source = probe.get("high_record_source_id")
        low_record = records.get(low_source)
        high_record = records.get(high_source)
        if low_record is None or high_record is None:
            raise ValueError(
                f"probe {name} refers to an unknown {probe_split} record"
            )
        if (
            low_record.get("split") != probe_split
            or high_record.get("split") != probe_split
        ):
            raise ValueError(
                "probe "
                f"{name} teacher-forced records must both be in {probe_split} split"
            )

        prefix = probe.get("prefix_tokens")
        if not isinstance(prefix, list) or not prefix:
            raise ValueError(f"probe {name} has no prefix_tokens")
        prefix_tuple = tuple(int(token) for token in prefix)
        divergence_index = int(
            probe.get("first_target_divergence_index", -1)
        )
        if divergence_index != len(prefix_tuple):
            raise ValueError(
                f"probe {name} divergence index does not match prefix length"
            )

        low_tokens = [int(token) for token in low_record["tokens"]]
        high_tokens = [int(token) for token in high_record["tokens"]]
        if low_tokens[:len(prefix_tuple)] != list(prefix_tuple):
            raise ValueError(
                f"probe {name} low record does not contain declared prefix"
            )
        if high_tokens[:len(prefix_tuple)] != list(prefix_tuple):
            raise ValueError(
                f"probe {name} high record does not contain declared prefix"
            )
        if (
            len(low_tokens) <= len(prefix_tuple)
            or len(high_tokens) <= len(prefix_tuple)
        ):
            raise ValueError(
                f"probe {name} has no target token at divergence"
            )
        low_target = low_tokens[len(prefix_tuple)]
        high_target = high_tokens[len(prefix_tuple)]
        if low_target == high_target:
            raise ValueError(
                f"probe {name} target tokens do not diverge"
            )

        grammar = validate_mozart_token_sequence(
            list(prefix_tuple),
            require_eos=False,
        )
        if not grammar["valid"]:
            raise ValueError(
                f"probe {name} prefix is not a valid MIDI grammar prefix: "
                f"{grammar['error']}"
            )

        low_controls = dict(probe["low_profile"])
        high_controls = dict(probe["high_profile"])
        if low_record["performance_controls"] != low_controls:
            raise ValueError(
                f"probe {name} low profile does not match the referenced record"
            )
        if high_record["performance_controls"] != high_controls:
            raise ValueError(
                f"probe {name} high profile does not match the referenced record"
            )

        steps: list[dict[str, Any]] = []
        for side, tokens, native_controls in (
            ("low", low_tokens, low_controls),
            ("high", high_tokens, high_controls),
        ):
            start_index = len(prefix_tuple)
            end_index = min(
                len(tokens) - 1,
                start_index + window_size,
            )
            for target_index in range(start_index, end_index):
                context = tokens[:target_index]
                target = tokens[target_index]
                grammar = validate_mozart_token_sequence(
                    context,
                    require_eos=False,
                )
                if not grammar["valid"]:
                    raise ValueError(
                        f"control {name} has invalid teacher-forced context "
                        f"at target index {target_index}: {grammar['error']}"
                    )
                if not _grammar_allowed_mask(context)[target]:
                    raise ValueError(
                        f"control {name} target token {target} is not legal "
                        f"after the teacher-forced context at index {target_index}"
                    )
                native_logits = _torch_next_logits(
                    model,
                    context,
                    native_controls,
                )
                opposite_controls = (
                    high_controls if side == "low" else low_controls
                )
                opposite_logits = _torch_next_logits(
                    model,
                    context,
                    opposite_controls,
                )
                distribution_total_variation = _token_distribution_total_variation(
                    native_logits,
                    opposite_logits,
                    context,
                    grammar_constrained=True,
                )
                native = _measure(
                    native_logits,
                    target,
                    context=context,
                )
                opposite = _measure(
                    opposite_logits,
                    target,
                    context=context,
                )
                target_probability_delta = (
                    native["target_probability"]
                    - opposite["target_probability"]
                )
                target_family_probability_delta = (
                    native["target_family_probability"]
                    - opposite["target_family_probability"]
                )
                if distribution_total_variation > 0.0:
                    target_probability_tv_alignment = (
                        target_probability_delta / distribution_total_variation
                    )
                else:
                    target_probability_tv_alignment = 0.0
                step: dict[str, Any] = {
                    "side": side,
                    "target_index": target_index,
                    "context_length": len(context),
                    "target_token": target,
                    "native": native,
                    "counterfactual": opposite,
                    "target_logit_delta_native_minus_counterfactual": (
                        native["target_logit"] - opposite["target_logit"]
                    ),
                    "target_probability_delta_native_minus_counterfactual": (
                        target_probability_delta
                    ),
                    "target_probability_tv_alignment": (
                        target_probability_tv_alignment
                    ),
                    "target_family_probability_delta_native_minus_counterfactual": (
                        target_family_probability_delta
                    ),
                    "target_family_directionally_correct": (
                        target_family_probability_delta > 0.0
                    ),
                    "target_directionally_correct": (
                        target_probability_delta > 0.0
                    ),
                    "top1_changed_by_control": (
                        native["top1_token"] != opposite["top1_token"]
                    ),
                    "distribution_total_variation_native_vs_counterfactual": distribution_total_variation,
                }
                if onnx_session is not None:
                    native_onnx_logits = _onnx_next_logits(
                        onnx_session,
                        context,
                        native_controls,
                    )
                    opposite_onnx_logits = _onnx_next_logits(
                        onnx_session,
                        context,
                        opposite_controls,
                    )
                    native_onnx = _measure(
                        native_onnx_logits,
                        target,
                        context=context,
                    )
                    opposite_onnx = _measure(
                        opposite_onnx_logits,
                        target,
                        context=context,
                    )
                    onnx_distribution_total_variation = _token_distribution_total_variation(
                        native_onnx_logits,
                        opposite_onnx_logits,
                        context,
                        grammar_constrained=True,
                    )
                    step["onnx_native"] = native_onnx
                    step["onnx_counterfactual"] = opposite_onnx
                    step["onnx_distribution_total_variation_native_vs_counterfactual"] = onnx_distribution_total_variation
                    if abs(distribution_total_variation - onnx_distribution_total_variation) > 1.0e-4:
                        failures.append(
                            "PyTorch/ONNX teacher-forced distribution-response mismatch "
                            f"for control {name} step {target_index}"
                        )
                    if (
                        native["top1_token"] != native_onnx["top1_token"]
                        or opposite["top1_token"]
                        != opposite_onnx["top1_token"]
                        or native["target_legal_top1"]
                        != native_onnx["target_legal_top1"]
                        or opposite["target_legal_top1"]
                        != opposite_onnx["target_legal_top1"]
                    ):
                        failures.append(
                            "PyTorch/ONNX teacher-forced top1 mismatch "
                            f"for control {name} step {target_index}"
                        )
                    if (
                        abs(
                            native["target_probability"]
                            - native_onnx["target_probability"]
                        ) > 1.0e-4
                        or abs(
                            opposite["target_probability"]
                            - opposite_onnx["target_probability"]
                        ) > 1.0e-4
                    ):
                        failures.append(
                            "PyTorch/ONNX teacher-forced target-probability mismatch "
                            f"for control {name} step {target_index}"
                        )
                    if (
                        native["target_legal_rank"]
                        != native_onnx["target_legal_rank"]
                        or opposite["target_legal_rank"]
                        != opposite_onnx["target_legal_rank"]
                    ):
                        failures.append(
                            "PyTorch/ONNX teacher-forced legal-rank mismatch "
                            f"for control {name} step {target_index}"
                        )
                    if (
                        abs(
                            native["target_family_probability"]
                            - native_onnx["target_family_probability"]
                        ) > 1.0e-4
                        or abs(
                            opposite["target_family_probability"]
                            - opposite_onnx["target_family_probability"]
                        ) > 1.0e-4
                    ):
                        failures.append(
                            "PyTorch/ONNX teacher-forced target-family probability mismatch "
                            f"for control {name} step {target_index}"
                        )
                steps.append(step)

        native_top1_count = sum(
            int(step["native"]["target_top1"])
            for step in steps
        )
        counterfactual_top1_count = sum(
            int(step["counterfactual"]["target_top1"])
            for step in steps
        )
        native_legal_top1_count = sum(
            int(step["native"]["target_legal_top1"])
            for step in steps
        )
        counterfactual_legal_top1_count = sum(
            int(step["counterfactual"]["target_legal_top1"])
            for step in steps
        )
        changed_steps = sum(
            int(step["top1_changed_by_control"])
            for step in steps
        )
        directionally_correct_steps = sum(
            int(step["target_directionally_correct"])
            for step in steps
        )
        family_directionally_correct_steps = sum(
            int(step["target_family_directionally_correct"])
            for step in steps
        )
        target_family_probability_deltas = [
            float(step["target_family_probability_delta_native_minus_counterfactual"])
            for step in steps
        ]
        target_logit_deltas = [
            float(step["target_logit_delta_native_minus_counterfactual"])
            for step in steps
        ]
        distribution_response_values = [
            float(step["distribution_total_variation_native_vs_counterfactual"])
            for step in steps
        ]
        target_probability_deltas = [
            float(step["target_probability_delta_native_minus_counterfactual"])
            for step in steps
        ]
        target_probability_tv_alignments = [
            float(step["target_probability_tv_alignment"])
            for step in steps
            if float(step["distribution_total_variation_native_vs_counterfactual"]) > 0.0
        ]

        low_divergence_step = next(
            step
            for step in steps
            if step["side"] == "low"
            and step["target_index"] == len(prefix_tuple)
        )
        high_divergence_step = next(
            step
            for step in steps
            if step["side"] == "high"
            and step["target_index"] == len(prefix_tuple)
        )
        low_target_report = dict(low_divergence_step["native"])
        high_target_report = dict(high_divergence_step["native"])
        low_target_probability_lift = float(
            low_divergence_step["target_probability_delta_native_minus_counterfactual"]
        )
        high_target_probability_lift = float(
            high_divergence_step["target_probability_delta_native_minus_counterfactual"]
        )
        control_effect = {
            "low_target_token": low_target_report["target_token"],
            "high_target_token": high_target_report["target_token"],
            "target_token_difference": (
                high_target_report["target_token"]
                - low_target_report["target_token"]
            ),
            "low_target_logit": low_target_report["target_logit"],
            "high_target_logit": high_target_report["target_logit"],
            "target_logit_difference": (
                high_target_report["target_logit"]
                - low_target_report["target_logit"]
            ),
            "low_target_top1": low_target_report["target_top1"],
            "high_target_top1": high_target_report["target_top1"],
            "low_target_probability_lift_native_minus_counterfactual": (
                low_target_probability_lift
            ),
            "high_target_probability_lift_native_minus_counterfactual": (
                high_target_probability_lift
            ),
            "low_target_directionally_correct": (
                low_target_probability_lift > 0.0
            ),
            "high_target_directionally_correct": (
                high_target_probability_lift > 0.0
            ),
        }

        entry: dict[str, Any] = {
            "prefix_tokens": list(prefix_tuple),
            "prefix_length": len(prefix_tuple),
            "low_controls": low_controls,
            "high_controls": high_controls,
            "targets_differ": low_target != high_target,
            "window_size_requested": window_size,
            "window_step_count": len(steps),
            "native_target_top1_count": native_top1_count,
            "counterfactual_target_top1_count": counterfactual_top1_count,
            "native_legal_target_top1_count": native_legal_top1_count,
            "counterfactual_legal_target_top1_count": (
                counterfactual_legal_top1_count
            ),
            "top1_changed_by_control_steps": changed_steps,
            "target_probability_directionally_correct_steps": (
                directionally_correct_steps
            ),
            "target_family_probability_directionally_correct_steps": (
                family_directionally_correct_steps
            ),
            "target_family_probability_directional_response_rate": (
                float(family_directionally_correct_steps / len(steps))
                if steps
                else 0.0
            ),
            "mean_target_family_probability_delta_native_minus_counterfactual": (
                float(np.mean(target_family_probability_deltas))
                if target_family_probability_deltas
                else 0.0
            ),
            "target_probability_directional_response_rate": (
                float(directionally_correct_steps / len(steps))
                if steps
                else 0.0
            ),
            "mean_target_probability_delta_native_minus_counterfactual": (
                float(np.mean(target_probability_deltas))
                if target_probability_deltas
                else 0.0
            ),
            "mean_target_probability_tv_alignment": (
                float(np.mean(target_probability_tv_alignments))
                if target_probability_tv_alignments
                else 0.0
            ),
            "mean_target_logit_delta_native_minus_counterfactual": (
                float(np.mean(target_logit_deltas))
                if target_logit_deltas
                else 0.0
            ),
            "mean_distribution_total_variation_native_vs_counterfactual": (
                float(np.mean(distribution_response_values))
                if distribution_response_values
                else 0.0
            ),
            "max_distribution_total_variation_native_vs_counterfactual": (
                float(np.max(distribution_response_values))
                if distribution_response_values
                else 0.0
            ),
            "min_distribution_total_variation_native_vs_counterfactual": (
                float(np.min(distribution_response_values))
                if distribution_response_values
                else 0.0
            ),
            "low_target": low_target_report,
            "high_target": high_target_report,
            "control_effect": control_effect,
            "steps": steps,
        }

        if require_target_top1 and (
            not low_target_report["target_top1"]
            or not high_target_report["target_top1"]
        ):
            failures.append(
                "teacher-forced divergence targets must both be top1 "
                f"for control {name}"
            )
        if require_legal_target_top1 and (
            not low_target_report["target_legal_top1"]
            or not high_target_report["target_legal_top1"]
        ):
            failures.append(
                "teacher-forced divergence targets must both be legal-token top1 "
                f"for control {name}"
            )

        report_controls[name] = entry

    observed_steps = sum(
        entry["window_step_count"]
        for entry in report_controls.values()
    )
    native_top1_steps = sum(
        entry["native_target_top1_count"]
        for entry in report_controls.values()
    )
    distribution_response_values = [
        float(step["distribution_total_variation_native_vs_counterfactual"])
        for entry in report_controls.values()
        for step in entry["steps"]
    ]
    target_probability_directionally_correct_steps = sum(
        int(step["target_directionally_correct"])
        for entry in report_controls.values()
        for step in entry["steps"]
    )
    target_family_probability_directionally_correct_steps = sum(
        int(step["target_family_directionally_correct"])
        for entry in report_controls.values()
        for step in entry["steps"]
    )
    target_family_probability_deltas = [
        float(step["target_family_probability_delta_native_minus_counterfactual"])
        for entry in report_controls.values()
        for step in entry["steps"]
    ]
    target_probability_deltas = [
        float(step["target_probability_delta_native_minus_counterfactual"])
        for entry in report_controls.values()
        for step in entry["steps"]
    ]
    target_probability_tv_alignments = [
        float(step["target_probability_tv_alignment"])
        for entry in report_controls.values()
        for step in entry["steps"]
        if float(step["distribution_total_variation_native_vs_counterfactual"]) > 0.0
    ]
    controls_with_both_targets_top1 = sum(
        int(
            entry["low_target"]["target_top1"]
            and entry["high_target"]["target_top1"]
        )
        for entry in report_controls.values()
    )
    controls_with_bidirectional_target_response = sum(
        int(
            entry["control_effect"]["low_target_directionally_correct"]
            and entry["control_effect"]["high_target_directionally_correct"]
        )
        for entry in report_controls.values()
    )
    native_legal_top1_steps = sum(
        entry["native_legal_target_top1_count"]
        for entry in report_controls.values()
    )
    counterfactual_legal_top1_steps = sum(
        entry["counterfactual_legal_target_top1_count"]
        for entry in report_controls.values()
    )
    controls_with_both_legal_targets_top1 = sum(
        int(
            entry["low_target"]["target_legal_top1"]
            and entry["high_target"]["target_legal_top1"]
        )
        for entry in report_controls.values()
    )

    return {
        "status": "FAIL" if failures else "PASS",
        "window_size": window_size,
        "require_target_top1": require_target_top1,
        "require_legal_target_top1": require_legal_target_top1,
        "control_count": len(PERFORMANCE_CONTROL_NAMES),
        "observed_teacher_forced_steps": observed_steps,
        "native_target_top1_steps": native_top1_steps,
        "native_legal_target_top1_steps": native_legal_top1_steps,
        "counterfactual_legal_target_top1_steps": counterfactual_legal_top1_steps,
        "controls_with_both_legal_targets_top1": (
            controls_with_both_legal_targets_top1
        ),
        "mean_distribution_total_variation_native_vs_counterfactual": (
            float(np.mean(distribution_response_values))
            if distribution_response_values
            else 0.0
        ),
        "max_distribution_total_variation_native_vs_counterfactual": (
            float(np.max(distribution_response_values))
            if distribution_response_values
            else 0.0
        ),
        "controls_with_both_targets_top1": controls_with_both_targets_top1,
        "controls_with_bidirectional_target_response": (
            controls_with_bidirectional_target_response
        ),
        "target_probability_directionally_correct_steps": (
            target_probability_directionally_correct_steps
        ),
        "target_family_probability_directionally_correct_steps": (
            target_family_probability_directionally_correct_steps
        ),
        "target_family_probability_directional_response_rate": (
            float(
                target_family_probability_directionally_correct_steps
                / observed_steps
            )
            if observed_steps
            else 0.0
        ),
        "mean_target_family_probability_delta_native_minus_counterfactual": (
            float(np.mean(target_family_probability_deltas))
            if target_family_probability_deltas
            else 0.0
        ),
        "target_probability_directional_response_rate": (
            float(
                target_probability_directionally_correct_steps / observed_steps
            )
            if observed_steps
            else 0.0
        ),
        "mean_target_probability_delta_native_minus_counterfactual": (
            float(np.mean(target_probability_deltas))
            if target_probability_deltas
            else 0.0
        ),
        "mean_target_probability_tv_alignment": (
            float(np.mean(target_probability_tv_alignments))
            if target_probability_tv_alignments
            else 0.0
        ),
        "controls": report_controls,
        "failures": failures,
    }


def evaluate_teacher_forced(
    checkpoint: Path,
    records_path: Path,
    probes_path: Path,
    *,
    config_path: Path | None = None,
    onnx_path: Path | None = None,
    window_size: int = 8,
    require_target_top1: bool = False,
    require_legal_target_top1: bool = False,
    probe_split: str = "train",
) -> dict[str, Any]:
    records = _load_records(records_path)
    probes = load_sequence_probe_file(probes_path)
    # load_sequence_probe_file returns only normalized prefixes; recover the
    # metadata needed to identify the exact low/high training records.
    raw_probes = json.loads(
        probes_path.read_text(encoding="utf-8")
    )
    for name in PERFORMANCE_CONTROL_NAMES:
        raw_entry = raw_probes["controls"][name]
        if name not in probes:
            raise ValueError(f"missing normalized probe for control {name}")
        normalized = dict(raw_entry)
        normalized["prefix_tokens"] = list(probes[name])
        raw_probes["controls"][name] = normalized

    model, _ = load_model(
        checkpoint,
        expected_config_path=config_path,
    )
    onnx_session = (
        _load_onnx_session(onnx_path)
        if onnx_path is not None
        else None
    )
    return _evaluate_with_model(
        model,
        records,
        raw_probes,
        onnx_session=onnx_session,
        window_size=window_size,
        require_target_top1=require_target_top1,
        require_legal_target_top1=require_legal_target_top1,
        probe_split=probe_split,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("records_jsonl", type=Path)
    parser.add_argument("probe_file", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--onnx", type=Path)
    parser.add_argument(
        "--window-size",
        type=int,
        default=8,
        help="Teacher-forced steps observed after each fixture divergence.",
    )
    parser.add_argument(
        "--require-target-top1",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Require both low/high target tokens to be top1 at the exact fixture divergence.",
    )
    parser.add_argument(
        "--require-legal-target-top1",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Require both low/high targets to be top1 within the grammar-legal token distribution.",
    )
    parser.add_argument(
        "--probe-split",
        choices=("train", "validation", "test"),
        default="train",
        help="Expected dataset split for the low/high probe records.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = evaluate_teacher_forced(
        args.checkpoint,
        args.records_jsonl,
        args.probe_file,
        config_path=args.config,
        onnx_path=args.onnx,
        window_size=args.window_size,
        require_target_top1=args.require_target_top1,
        require_legal_target_top1=args.require_legal_target_top1,
        probe_split=args.probe_split,
    )
    encoded = json.dumps(
        report,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
