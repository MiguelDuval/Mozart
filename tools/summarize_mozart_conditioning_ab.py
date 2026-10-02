#!/usr/bin/env python3
"""Summarize the manual Mozart context-diversity A/B experiment.

This is a development QA/reporting tool. It compares the matched-exposure
control with the context-diverse fit and does not define a production model
selection rule or tensor ABI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_fit(path: Path) -> dict[str, Any] | None:
    try:
        import torch

        if not path.exists():
            return None
        checkpoint = torch.load(
            path,
            map_location="cpu",
            weights_only=False,
        )
    except (OSError, RuntimeError, ValueError, ImportError):
        return None

    if not isinstance(checkpoint, dict):
        return None

    return {
        "epoch": checkpoint.get("epoch"),
        "train_loss": checkpoint.get("train_loss"),
        "validation_loss": checkpoint.get("validation_loss"),
        "total_optimizer_updates": checkpoint.get("total_optimizer_updates"),
        "repeat_train_records": checkpoint.get("repeat_train_records"),
    }


def summarize_teacher(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None
    keys = (
        "status",
        "observed_teacher_forced_steps",
        "native_target_top1_steps",
        "native_legal_target_top1_steps",
        "controls_with_both_legal_targets_top1",
        "controls_with_bidirectional_target_response",
        "target_probability_directional_response_rate",
        "target_family_probability_directional_response_rate",
        "mean_target_probability_delta_native_minus_counterfactual",
        "mean_target_family_probability_delta_native_minus_counterfactual",
        "mean_target_probability_tv_alignment",
        "mean_distribution_total_variation_native_vs_counterfactual",
    )
    return {key: report.get(key) for key in keys}


def summarize_sequence(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None

    controls = report.get("controls")
    if not isinstance(controls, dict):
        controls = {}

    sequence_changed = 0
    max_tvs: list[float] = []
    for entry in controls.values():
        if not isinstance(entry, dict):
            continue
        torch_report = entry.get("torch")
        if not isinstance(torch_report, dict):
            torch_report = {}
        if torch_report.get("sequence_changed") is True:
            sequence_changed += 1
        response = torch_report.get("distribution_response")
        if not isinstance(response, dict):
            response = {}
        value = response.get("max_total_variation")
        if isinstance(value, (int, float)):
            max_tvs.append(float(value))

    keys = (
        "status",
        "grammar_constrained",
        "require_valid_grammar",
        "require_distribution_response",
        "min_distribution_total_variation",
        "max_generated_tokens",
        "failures",
    )
    summary = {key: report.get(key) for key in keys}
    summary["controls_with_sequence_change"] = sequence_changed
    summary["mean_control_max_total_variation"] = (
        sum(max_tvs) / len(max_tvs) if max_tvs else None
    )
    summary["min_control_max_total_variation"] = (
        min(max_tvs) if max_tvs else None
    )
    summary["max_control_max_total_variation"] = (
        max(max_tvs) if max_tvs else None
    )
    return summary


def subtract(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def compare_experiments(
    matched: dict[str, Any] | None,
    diverse: dict[str, Any] | None,
) -> dict[str, dict[str, Any]] | None:
    if matched is None or diverse is None:
        return None

    matched_controls = matched.get("controls")
    diverse_controls = diverse.get("controls")
    if not isinstance(matched_controls, dict) or not isinstance(diverse_controls, dict):
        return None

    comparison: dict[str, dict[str, Any]] = {}
    for name in sorted(set(matched_controls) & set(diverse_controls)):
        matched_entry = matched_controls[name]
        diverse_entry = diverse_controls[name]
        if not isinstance(matched_entry, dict) or not isinstance(diverse_entry, dict):
            continue

        matched_torch = matched_entry.get("torch")
        diverse_torch = diverse_entry.get("torch")
        if not isinstance(matched_torch, dict) or not isinstance(diverse_torch, dict):
            continue

        matched_response = matched_torch.get("distribution_response")
        diverse_response = diverse_torch.get("distribution_response")
        if not isinstance(matched_response, dict) or not isinstance(diverse_response, dict):
            continue

        comparison[name] = {
            "sequence_changed_delta": (
                int(bool(diverse_torch.get("sequence_changed")))
                - int(bool(matched_torch.get("sequence_changed")))
            ),
            "max_total_variation_delta": subtract(
                diverse_response.get("max_total_variation"),
                matched_response.get("max_total_variation"),
            ),
            "mean_total_variation_delta": subtract(
                diverse_response.get("mean_total_variation"),
                matched_response.get("mean_total_variation"),
            ),
        }
    return comparison


def build_summary(
    *,
    baseline_fit: dict[str, Any] | None,
    matched_fit: dict[str, Any] | None,
    diverse_fit: dict[str, Any] | None,
    baseline_teacher: dict[str, Any] | None,
    matched_teacher: dict[str, Any] | None,
    diverse_teacher: dict[str, Any] | None,
    baseline_sequence: dict[str, Any] | None,
    matched_sequence: dict[str, Any] | None,
    diverse_sequence: dict[str, Any] | None,
) -> dict[str, Any]:
    reports = (
        baseline_teacher,
        matched_teacher,
        diverse_teacher,
        baseline_sequence,
        matched_sequence,
        diverse_sequence,
    )
    available_statuses = [
        report.get("status")
        for report in reports
        if isinstance(report, dict) and isinstance(report.get("status"), str)
    ]

    required = {
        "matched_teacher_forced": matched_teacher,
        "matched_sequence": matched_sequence,
        "context_diverse_teacher_forced": diverse_teacher,
        "context_diverse_sequence": diverse_sequence,
    }
    missing = [name for name, report in required.items() if report is None]

    if not available_statuses:
        status = "NO_REPORTS"
    elif any(value != "PASS" for value in available_statuses):
        status = "FAIL"
    elif missing:
        status = "PARTIAL"
    else:
        status = "PASS"

    matched_teacher_summary = summarize_teacher(matched_teacher)
    diverse_teacher_summary = summarize_teacher(diverse_teacher)
    matched_sequence_summary = summarize_sequence(matched_sequence)
    diverse_sequence_summary = summarize_sequence(diverse_sequence)

    teacher_delta = None
    if matched_teacher_summary is not None and diverse_teacher_summary is not None:
        teacher_delta = {
            "target_probability_directional_response_rate_delta": subtract(
                diverse_teacher_summary.get(
                    "target_probability_directional_response_rate"
                ),
                matched_teacher_summary.get(
                    "target_probability_directional_response_rate"
                ),
            ),
            "target_family_probability_directional_response_rate_delta": subtract(
                diverse_teacher_summary.get(
                    "target_family_probability_directional_response_rate"
                ),
                matched_teacher_summary.get(
                    "target_family_probability_directional_response_rate"
                ),
            ),
            "mean_target_probability_delta_delta": subtract(
                diverse_teacher_summary.get(
                    "mean_target_probability_delta_native_minus_counterfactual"
                ),
                matched_teacher_summary.get(
                    "mean_target_probability_delta_native_minus_counterfactual"
                ),
            ),
            "mean_target_family_probability_delta_delta": subtract(
                diverse_teacher_summary.get(
                    "mean_target_family_probability_delta_native_minus_counterfactual"
                ),
                matched_teacher_summary.get(
                    "mean_target_family_probability_delta_native_minus_counterfactual"
                ),
            ),
            "mean_distribution_total_variation_delta": subtract(
                diverse_teacher_summary.get(
                    "mean_distribution_total_variation_native_vs_counterfactual"
                ),
                matched_teacher_summary.get(
                    "mean_distribution_total_variation_native_vs_counterfactual"
                ),
            ),
        }

    sequence_delta = None
    if matched_sequence_summary is not None and diverse_sequence_summary is not None:
        sequence_delta = {
            "controls_with_sequence_change_delta": (
                int(diverse_sequence_summary.get("controls_with_sequence_change") or 0)
                - int(matched_sequence_summary.get("controls_with_sequence_change") or 0)
            ),
            "mean_control_max_total_variation_delta": subtract(
                diverse_sequence_summary.get("mean_control_max_total_variation"),
                matched_sequence_summary.get("mean_control_max_total_variation"),
            ),
            "min_control_max_total_variation_delta": subtract(
                diverse_sequence_summary.get("min_control_max_total_variation"),
                matched_sequence_summary.get("min_control_max_total_variation"),
            ),
            "max_control_max_total_variation_delta": subtract(
                diverse_sequence_summary.get("max_control_max_total_variation"),
                matched_sequence_summary.get("max_control_max_total_variation"),
            ),
        }

    return {
        "status": status,
        "missing_required_reports": missing,
        "baseline_regular": {
            "fit": baseline_fit,
            "teacher_forced": summarize_teacher(baseline_teacher),
            "grammar_constrained_sequence": summarize_sequence(baseline_sequence),
        },
        "baseline_matched_exposure": {
            "fit": matched_fit,
            "teacher_forced": matched_teacher_summary,
            "grammar_constrained_sequence": matched_sequence_summary,
        },
        "context_diverse": {
            "fit": diverse_fit,
            "teacher_forced": diverse_teacher_summary,
            "grammar_constrained_sequence": diverse_sequence_summary,
        },
        "diverse_minus_matched": {
            "fit": {
                "train_loss_delta": subtract(
                    diverse_fit.get("train_loss") if diverse_fit else None,
                    matched_fit.get("train_loss") if matched_fit else None,
                ),
                "validation_loss_delta": subtract(
                    diverse_fit.get("validation_loss") if diverse_fit else None,
                    matched_fit.get("validation_loss") if matched_fit else None,
                ),
            },
            "teacher_forced": teacher_delta,
            "grammar_constrained_sequence": sequence_delta,
            "per_control_autoregressive": compare_experiments(
                matched_sequence,
                diverse_sequence,
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--matched-dir", type=Path, required=True)
    parser.add_argument("--diverse-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = build_summary(
        baseline_fit=load_fit(args.baseline_dir / "latest.pt"),
        matched_fit=load_fit(args.matched_dir / "latest.pt"),
        diverse_fit=load_fit(args.diverse_dir / "latest.pt"),
        baseline_teacher=load_json(
            args.baseline_dir / "conditioning-teacher-forced.json"
        ),
        matched_teacher=load_json(
            args.matched_dir / "conditioning-teacher-forced.json"
        ),
        diverse_teacher=load_json(
            args.diverse_dir / "conditioning-teacher-forced.json"
        ),
        baseline_sequence=load_json(
            args.baseline_dir / "conditioning-sequence-grammar-constrained.json"
        ),
        matched_sequence=load_json(
            args.matched_dir / "conditioning-sequence-grammar-constrained.json"
        ),
        diverse_sequence=load_json(
            args.diverse_dir / "conditioning-sequence-grammar-constrained.json"
        ),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    # Diagnostic FAIL is data, not a CI gate. Syntax/I/O/runtime errors still fail normally.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
