#!/usr/bin/env python3
"""Measure compositional categorical conditioning in teacher-forced and AR modes.

This is a diagnostic-only experiment. Training exposes one categorical axis at
a time; evaluation queries unseen combinations of multiple axes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from mozart_model import ModelConfig, MozartTransformer, conditioning_ids
from mozart_token_grammar import EOS, allowed_next_token_ranges

CATEGORICAL_NAMES = ("style", "substyle", "mood", "rhythm", "role")
CONTROL_NAMES = ("density", "energy", "syncopation", "swing", "variation")


def _load_model(checkpoint_path: Path, config_path: Path) -> MozartTransformer:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("model_state"), dict):
        raise ValueError("checkpoint must contain model_state")
    model = MozartTransformer(ModelConfig.from_json(config_path))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model


def _load_records(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{path}:{number}: invalid source_id")
        if source_id in records:
            raise ValueError(f"{path}:{number}: duplicate source_id {source_id!r}")
        records[source_id] = record
    if not records:
        raise ValueError(f"{path}: no records")
    return records


def _load_probes(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    compositions = payload.get("compositions")
    if not isinstance(compositions, dict) or not compositions:
        raise ValueError("composition probe file must contain compositions")
    return payload


def _controls_tensor(controls: dict[str, float]) -> torch.Tensor:
    values = [float(controls[name]) for name in CONTROL_NAMES]
    if any(not 0.0 <= value <= 1.0 for value in values):
        raise ValueError("performance controls must be in [0, 1]")
    return torch.tensor([values], dtype=torch.float32)


def _ids(conditioning: dict[str, str]) -> dict[str, int]:
    return conditioning_ids({"conditioning": {**conditioning, "seed": 0}})


def _torch_logits(model: MozartTransformer, tokens: list[int], conditioning: dict[str, str], controls: dict[str, float]) -> np.ndarray:
    ids = _ids(conditioning)
    with torch.inference_mode():
        logits = model(
            torch.tensor([tokens], dtype=torch.long),
            torch.tensor([ids["style"]]),
            torch.tensor([ids["substyle"]]),
            torch.tensor([ids["mood"]]),
            torch.tensor([ids["rhythm"]]),
            torch.tensor([ids["role"]]),
            _controls_tensor(controls),
        )
    value = logits[0, -1].detach().cpu().float().numpy()
    if value.shape != (512,) or not np.isfinite(value).all():
        raise ValueError("PyTorch logits must be finite [512]")
    return value


def _onnx_logits(session: Any, tokens: list[int], conditioning: dict[str, str], controls: dict[str, float]) -> np.ndarray:
    ids = _ids(conditioning)
    outputs = session.run(
        ["logits"],
        {
            "input_ids": np.asarray([tokens], dtype=np.int64),
            "style_id": np.asarray([ids["style"]], dtype=np.int64),
            "substyle_id": np.asarray([ids["substyle"]], dtype=np.int64),
            "mood_id": np.asarray([ids["mood"]], dtype=np.int64),
            "rhythm_id": np.asarray([ids["rhythm"]], dtype=np.int64),
            "role_id": np.asarray([ids["role"]], dtype=np.int64),
            "performance_controls": np.asarray(
                [[float(controls[name]) for name in CONTROL_NAMES]],
                dtype=np.float32,
            ),
        },
    )
    value = np.asarray(outputs[0])
    if value.ndim != 3 or tuple(value.shape) != (1, len(tokens), 512):
        raise ValueError(f"unexpected ONNX logits shape: {tuple(value.shape)}")
    result = value[0, -1].astype(np.float32, copy=False)
    if not np.isfinite(result).all():
        raise ValueError("ONNX logits must be finite [512]")
    return result


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits.astype(np.float64) - np.max(logits)
    probabilities = np.exp(shifted)
    probabilities /= np.sum(probabilities)
    return probabilities


def _tv(left: np.ndarray, right: np.ndarray) -> float:
    return float(0.5 * np.abs(_softmax(left) - _softmax(right)).sum())


def _target_probability(logits: np.ndarray, target: int) -> float:
    return float(_softmax(logits)[target])


def _center(values: np.ndarray) -> np.ndarray:
    return values - np.mean(values)


def _additivity(base: np.ndarray, singles: list[np.ndarray], combo: np.ndarray) -> dict[str, float]:
    centered_base = _center(base)
    actual = _center(combo - base)
    expected = _center(np.sum([single - base for single in singles], axis=0))
    residual = actual - expected
    actual_norm = float(np.linalg.norm(actual))
    residual_norm = float(np.linalg.norm(residual))
    denom = float(np.linalg.norm(actual) * np.linalg.norm(expected))
    cosine = float(np.dot(actual, expected) / denom) if denom > 1e-12 else 0.0
    expected = expected.astype(np.float64, copy=False)
    actual = actual.astype(np.float64, copy=False)
    return {
        "centered_actual_delta_l2": actual_norm,
        "centered_additive_expected_delta_l2": float(np.linalg.norm(expected)),
        "centered_interaction_residual_l2": residual_norm,
        "interaction_residual_ratio": residual_norm / actual_norm if actual_norm > 1e-12 else 0.0,
        "actual_vs_additive_cosine": cosine,
        "base_centered_logit_l2": float(np.linalg.norm(centered_base)),
    }


def _allowed_mask(tokens: list[int]) -> np.ndarray:
    mask = np.zeros(512, dtype=bool)
    for start, end in allowed_next_token_ranges(tokens):
        mask[start:end] = True
    if not np.any(mask):
        raise ValueError("Mozart grammar has no valid next token")
    return mask


def _autoregressive(model: MozartTransformer, session: Any, probe: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    prefix = [int(x) for x in probe["prefix_tokens"]]
    controls = dict(probe["performance_controls"])
    base_conditioning = dict(probe["low_conditioning"])
    combo_conditioning = dict(probe["high_conditioning"])
    low_tokens = list(prefix)
    high_tokens = list(prefix)
    tv_values: list[float] = []
    parity_max = 0.0

    for _ in range(max_tokens):
        low_logits = _torch_logits(model, low_tokens, base_conditioning, controls)
        high_logits = _torch_logits(model, high_tokens, combo_conditioning, controls)
        tv_values.append(_tv(low_logits, high_logits))
        if session is not None:
            low_onnx = _onnx_logits(session, low_tokens, base_conditioning, controls)
            high_onnx = _onnx_logits(session, high_tokens, combo_conditioning, controls)
            parity = max(
                float(np.max(np.abs(low_logits - low_onnx))),
                float(np.max(np.abs(high_logits - high_onnx))),
            )
            parity_max = max(parity_max, parity)
            if parity > 5e-4:
                raise RuntimeError(f"PyTorch/ONNX AR parity exceeded tolerance: {parity}")
        low_token = int(np.argmax(np.where(_allowed_mask(low_tokens), low_logits, -np.inf)))
        high_token = int(np.argmax(np.where(_allowed_mask(high_tokens), high_logits, -np.inf)))
        low_tokens.append(low_token)
        high_tokens.append(high_token)
        if low_token != high_token or low_token == EOS or high_token == EOS:
            break

    common = 0
    for left, right in zip(low_tokens, high_tokens):
        if left != right:
            break
        common += 1
    return {
        "sequence_changed": common != len(low_tokens) or common != len(high_tokens),
        "observed_shared_context_count": len(tv_values),
        "first_shared_context_total_variation": tv_values[0] if tv_values else 0.0,
        "last_shared_context_total_variation": tv_values[-1] if tv_values else 0.0,
        "max_total_variation": max(tv_values) if tv_values else 0.0,
        "mean_total_variation": float(np.mean(tv_values)) if tv_values else 0.0,
        "parity_max_abs_error": parity_max,
        "generated_low_tokens": len(low_tokens) - len(prefix),
        "generated_high_tokens": len(high_tokens) - len(prefix),
        "first_divergence_generated_index": common - len(prefix) if common != len(low_tokens) or common != len(high_tokens) else None,
    }


def evaluate(model: MozartTransformer, probes: dict[str, Any], records: dict[str, dict[str, Any]], session: Any, *, window_size: int, max_tokens: int) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for profile, probe in probes["compositions"].items():
        base_record = records[probe["low_record_source_id"]]
        combo_record = records[probe["high_record_source_id"]]
        base_tokens = [int(x) for x in base_record["tokens"]]
        combo_tokens = [int(x) for x in combo_record["tokens"]]
        prefix = [int(x) for x in probe["prefix_tokens"]]
        divergence = len(prefix)
        controls = dict(probe["performance_controls"])

        steps = []
        parity_max = 0.0
        for target_index in range(divergence, min(len(base_tokens), divergence + window_size + 1)):
            context = base_tokens[:target_index]
            target = base_tokens[target_index]
            base_logits = _torch_logits(model, context, probe["low_conditioning"], controls)
            single_logits = []
            for axis in probe["axes"]:
                single = dict(probe["low_conditioning"])
                single[axis] = probe["high_conditioning"][axis]
                single_logits.append(_torch_logits(model, context, single, controls))
            combo_logits = _torch_logits(model, context, probe["high_conditioning"], controls)
            target_combo = combo_tokens[target_index]
            steps.append({
                "target_index": target_index,
                "context_length": len(context),
                "base_target_probability": _target_probability(base_logits, target),
                "combo_target_probability_on_base_target": _target_probability(combo_logits, target),
                "combo_target_probability_on_combo_target": _target_probability(combo_logits, target_combo),
                "base_vs_combo_total_variation": _tv(base_logits, combo_logits),
                "target_probability_delta": _target_probability(combo_logits, target) - _target_probability(base_logits, target),
            })
            if session is not None:
                for cond, logits in [(probe["low_conditioning"], base_logits), *[
                    ({**probe["low_conditioning"], axis: probe["high_conditioning"][axis]}, single_logits[i])
                    for i, axis in enumerate(probe["axes"])
                ], (probe["high_conditioning"], combo_logits)]:
                    onnx = _onnx_logits(session, context, cond, controls)
                    parity_max = max(parity_max, float(np.max(np.abs(logits - onnx))))
                if parity_max > 5e-4:
                    raise RuntimeError(f"PyTorch/ONNX TF parity exceeded tolerance: {parity_max}")

        # First-divergence additivity is deliberately a logit-space diagnostic.
        context = base_tokens[:divergence]
        base_logits = _torch_logits(model, context, probe["low_conditioning"], controls)
        singles = [
            _torch_logits(
                model,
                context,
                {**probe["low_conditioning"], axis: probe["high_conditioning"][axis]},
                controls,
            )
            for axis in probe["axes"]
        ]
        combo_logits = _torch_logits(model, context, probe["high_conditioning"], controls)
        additivity = _additivity(base_logits, singles, combo_logits)
        results[profile] = {
            "axes": probe["axes"],
            "teacher_forced": {
                "window_step_count": len(steps),
                "mean_target_probability_delta": float(np.mean([s["target_probability_delta"] for s in steps])) if steps else 0.0,
                "mean_base_vs_combo_total_variation": float(np.mean([s["base_vs_combo_total_variation"] for s in steps])) if steps else 0.0,
                "divergence_target_probability_delta": steps[0]["target_probability_delta"] if steps else 0.0,
                "parity_max_abs_error": parity_max,
            },
            "logit_additivity_at_divergence": additivity,
            "autoregressive": _autoregressive(model, session, probe, max_tokens),
        }
    return {
        "status": "PASS",
        "semantic_gate": "diagnostic-only",
        "training_regime": "single-axis-only",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("records", type=Path)
    parser.add_argument("probes", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--onnx", type=Path)
    parser.add_argument("--window-size", type=int, default=8)
    parser.add_argument("--max-generated-tokens", type=int, default=32)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    model = _load_model(args.checkpoint, args.config)
    records = _load_records(args.records)
    probes = _load_probes(args.probes)
    session = None
    if args.onnx is not None:
        import onnxruntime as ort
        session = ort.InferenceSession(str(args.onnx), providers=["CPUExecutionProvider"])
    report = evaluate(model, probes, records, session, window_size=args.window_size, max_tokens=args.max_generated_tokens)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
