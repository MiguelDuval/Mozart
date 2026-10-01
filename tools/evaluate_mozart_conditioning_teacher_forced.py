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
    _onnx_next_logits,
    _torch_next_logits,
    load_sequence_probe_file,
    validate_mozart_token_sequence,
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


def _measure(logits: np.ndarray, target: int) -> dict[str, Any]:
    if not np.isfinite(logits).all():
        raise ValueError("logits contain non-finite values")
    rank = _target_rank(logits, target)
    top1 = int(np.argmax(logits))
    target_logit = float(logits[target])
    top1_logit = float(logits[top1])
    return {
        "target_token": target,
        "target_rank": rank,
        "target_top1": top1 == target,
        "target_logit": target_logit,
        "top1_token": top1,
        "top1_logit": top1_logit,
        "target_top1_margin": target_logit - top1_logit,
    }


def _evaluate_with_model(
    model: Any,
    records: dict[str, dict[str, Any]],
    probes: dict[str, Any],
    *,
    onnx_session: Any | None = None,
    window_size: int = 8,
    require_target_top1: bool = False,
) -> dict[str, Any]:
    controls = probes.get("controls")
    if not isinstance(controls, dict):
        raise ValueError("probe file controls must be an object")
    if window_size <= 0:
        raise ValueError("window_size must be positive")

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
                f"probe {name} refers to an unknown train record"
            )
        if (
            low_record.get("split") != "train"
            or high_record.get("split") != "train"
        ):
            raise ValueError(
                f"probe {name} teacher-forced records must both be in train split"
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
                native = _measure(native_logits, target)
                opposite = _measure(opposite_logits, target)
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
                    "top1_changed_by_control": (
                        native["top1_token"] != opposite["top1_token"]
                    ),
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
                    )
                    opposite_onnx = _measure(
                        opposite_onnx_logits,
                        target,
                    )
                    step["onnx_native"] = native_onnx
                    step["onnx_counterfactual"] = opposite_onnx
                    if (
                        native["top1_token"] != native_onnx["top1_token"]
                        or opposite["top1_token"]
                        != opposite_onnx["top1_token"]
                    ):
                        failures.append(
                            "PyTorch/ONNX teacher-forced top1 mismatch "
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
        changed_steps = sum(
            int(step["top1_changed_by_control"])
            for step in steps
        )
        target_logit_deltas = [
            float(step["target_logit_delta_native_minus_counterfactual"])
            for step in steps
        ]

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
            "top1_changed_by_control_steps": changed_steps,
            "mean_target_logit_delta_native_minus_counterfactual": (
                float(np.mean(target_logit_deltas))
                if target_logit_deltas
                else 0.0
            ),
            "steps": steps,
        }

        if require_target_top1 and native_top1_count < len(steps):
            failures.append(
                "teacher-forced target is not top1 for every observed step "
                f"of control {name}"
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

    return {
        "status": "FAIL" if failures else "PASS",
        "window_size": window_size,
        "require_target_top1": require_target_top1,
        "control_count": len(PERFORMANCE_CONTROL_NAMES),
        "observed_teacher_forced_steps": observed_steps,
        "native_target_top1_steps": native_top1_steps,
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
