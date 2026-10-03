#!/usr/bin/env python3
"""Measure categorical conditioning in teacher-forced and autoregressive modes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from mozart_model import ModelConfig, MozartTransformer, conditioning_ids
from mozart_token_grammar import EOS, allowed_next_token_ranges


def _load_model(checkpoint_path: Path, config_path: Path) -> tuple[MozartTransformer, ModelConfig]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("model_state"), dict):
        raise ValueError("checkpoint must contain model_state")
    config = ModelConfig.from_json(config_path)
    model = MozartTransformer(config)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, config


def _load_records(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{path}:{line_number}: invalid source_id")
        if source_id in records:
            raise ValueError(f"{path}:{line_number}: duplicate source_id {source_id!r}")
        records[source_id] = record
    if not records:
        raise ValueError(f"{path}: no records")
    return records


def _load_probes(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    probes = payload.get("probes")
    if not isinstance(probes, dict) or set(probes) != {"style", "substyle", "mood", "rhythm", "role"}:
        raise ValueError("categorical probe file must contain exactly five axes")
    return payload


def _controls_tensor(values: dict[str, float]) -> torch.Tensor:
    names = ("density", "energy", "syncopation", "swing", "variation")
    ordered = [float(values[name]) for name in names]
    if any(not 0.0 <= value <= 1.0 for value in ordered):
        raise ValueError("performance controls must be in [0, 1]")
    return torch.tensor([ordered], dtype=torch.float32)


def _torch_logits(
    model: MozartTransformer,
    tokens: list[int],
    conditioning: dict[str, str],
    controls: dict[str, float],
) -> np.ndarray:
    ids = conditioning_ids({"conditioning": {**conditioning, "seed": 0}})
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
    ids = conditioning_ids({**conditioning, "seed": 0})
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
                [[float(controls[name]) for name in ("density", "energy", "syncopation", "swing", "variation")]],
                dtype=np.float32,
            ),
        },
    )
    if not outputs:
        raise ValueError("ONNX returned no logits")
    value = np.asarray(outputs[0])
    if value.ndim != 3 or tuple(value.shape) != (1, len(tokens), 512):
        raise ValueError(f"unexpected ONNX logits shape: {tuple(value.shape)}")
    result = value[0, -1].astype(np.float32, copy=False)
    if not np.isfinite(result).all():
        raise ValueError("ONNX logits must be finite [512]")
    return result


def _load_onnx(path: Path) -> Any:
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("onnxruntime is required when --onnx is supplied") from exc
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values.astype(np.float64) - np.max(values)
    probabilities = np.exp(shifted)
    probabilities /= np.sum(probabilities)
    return probabilities


def _target_probability(logits: np.ndarray, target: int) -> float:
    return float(_softmax(logits)[target])


def _tv(left: np.ndarray, right: np.ndarray) -> float:
    return float(0.5 * np.abs(_softmax(left) - _softmax(right)).sum())


def _longest_common_prefix(left: list[int], right: list[int]) -> int:
    index = 0
    limit = min(len(left), len(right))
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def _teacher_forced_pair(
    model: MozartTransformer,
    session: Any,
    probe: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    window_size: int,
) -> dict[str, Any]:
    low = records[probe["low_record_source_id"]]
    high = records[probe["high_record_source_id"]]
    if low.get("split") != "test" or high.get("split") != "test":
        raise ValueError("categorical teacher-forced probes must reference test records")
    prefix = [int(x) for x in probe["prefix_tokens"]]
    if not prefix:
        raise ValueError("categorical probe prefix must not be empty")
    low_tokens = [int(x) for x in low["tokens"]]
    high_tokens = [int(x) for x in high["tokens"]]
    if low_tokens[:len(prefix)] != prefix or high_tokens[:len(prefix)] != prefix:
        raise ValueError("test records do not contain their declared probe prefix")
    divergence = len(prefix)
    if low_tokens[divergence] == high_tokens[divergence]:
        raise ValueError("categorical probe targets must differ")

    low_conditioning = dict(probe["low_conditioning"])
    high_conditioning = dict(probe["high_conditioning"])
    controls = dict(probe["performance_controls"])
    steps: list[dict[str, Any]] = []
    parity_max = 0.0

    for side, tokens, native, opposite in (
        ("low", low_tokens, low_conditioning, high_conditioning),
        ("high", high_tokens, high_conditioning, low_conditioning),
    ):
        end = min(len(tokens), divergence + window_size + 1)
        for target_index in range(divergence, end):
            context = tokens[:target_index]
            target = tokens[target_index]
            native_logits = _torch_logits(model, context, native, controls)
            opposite_logits = _torch_logits(model, context, opposite, controls)
            native_probability = _target_probability(native_logits, target)
            opposite_probability = _target_probability(opposite_logits, target)
            entry = {
                "side": side,
                "target_index": target_index,
                "context_length": len(context),
                "target_token": target,
                "target_probability_delta": native_probability - opposite_probability,
                "distribution_total_variation": _tv(native_logits, opposite_logits),
            }
            if session is not None:
                native_onnx = _onnx_logits(session, context, native, controls)
                opposite_onnx = _onnx_logits(session, context, opposite, controls)
                parity = max(
                    float(np.max(np.abs(native_logits - native_onnx))),
                    float(np.max(np.abs(opposite_logits - opposite_onnx))),
                )
                parity_max = max(parity_max, parity)
                entry["onnx_distribution_total_variation"] = _tv(native_onnx, opposite_onnx)
                if parity > 5.0e-4:
                    raise RuntimeError(f"PyTorch/ONNX parity exceeded tolerance: {parity}")
            steps.append(entry)

    deltas = [float(step["target_probability_delta"]) for step in steps]
    tvs = [float(step["distribution_total_variation"]) for step in steps]
    divergence_steps = [step for step in steps if step["target_index"] == divergence]
    return {
        "window_step_count": len(steps),
        "target_probability_directional_response_rate": (
            sum(delta > 0.0 for delta in deltas) / len(deltas)
            if deltas else 0.0
        ),
        "mean_target_probability_delta": float(np.mean(deltas)) if deltas else 0.0,
        "mean_distribution_total_variation": float(np.mean(tvs)) if tvs else 0.0,
        "divergence_target_probability_delta_low": float(
            next(step["target_probability_delta"] for step in divergence_steps if step["side"] == "low")
        ),
        "divergence_target_probability_delta_high": float(
            next(step["target_probability_delta"] for step in divergence_steps if step["side"] == "high")
        ),
        "parity_max_abs_error": parity_max,
    }


def _autoregressive_pair(
    model: MozartTransformer,
    session: Any,
    probe: dict[str, Any],
    *,
    max_tokens: int,
) -> dict[str, Any]:
    prefix = [int(x) for x in probe["prefix_tokens"]]
    controls = dict(probe["performance_controls"])
    low = dict(probe["low_conditioning"])
    high = dict(probe["high_conditioning"])

    def next_logits(tokens: list[int], conditioning: dict[str, str], controls_: dict[str, float]) -> np.ndarray:
        return _torch_logits(model, tokens, conditioning, controls_)

    low_tokens = list(prefix)
    high_tokens = list(prefix)
    low_full = list(prefix)
    high_full = list(prefix)
    tv_values: list[float] = []
    parity_max = 0.0

    for _ in range(max_tokens):
        low_logits = next_logits(low_tokens, low, controls)
        high_logits = next_logits(high_tokens, high, controls)
        tv_values.append(_tv(low_logits, high_logits))

        def allowed_mask(tokens: list[int]) -> np.ndarray:
            mask = np.zeros(512, dtype=bool)
            for start, end in allowed_next_token_ranges(tokens):
                mask[start:end] = True
            if not np.any(mask):
                raise ValueError("Mozart grammar has no valid next token")
            return mask

        if session is not None:
            low_onnx = _onnx_logits(session, low_tokens, low, controls)
            high_onnx = _onnx_logits(session, high_tokens, high, controls)
            parity = max(
                float(np.max(np.abs(low_logits - low_onnx))),
                float(np.max(np.abs(high_logits - high_onnx))),
            )
            parity_max = max(parity_max, parity)
            if parity > 5.0e-4:
                raise RuntimeError(f"PyTorch/ONNX AR parity exceeded tolerance: {parity}")

        low_allowed = allowed_mask(low_tokens)
        high_allowed = allowed_mask(high_tokens)
        low_token = int(np.argmax(np.where(low_allowed, low_logits, -np.inf)))
        high_token = int(np.argmax(np.where(high_allowed, high_logits, -np.inf)))
        low_tokens.append(low_token)
        high_tokens.append(high_token)
        low_full.append(low_token)
        high_full.append(high_token)
        if low_token != high_token or low_token == EOS or high_token == EOS:
            break

    common = _longest_common_prefix(low_full, high_full)
    changed = len(low_full) != len(high_full) or common < len(low_full) or common < len(high_full)
    return {
        "sequence_changed": changed,
        "observed_shared_context_count": len(tv_values),
        "first_shared_context_total_variation": tv_values[0] if tv_values else 0.0,
        "last_shared_context_total_variation": tv_values[-1] if tv_values else 0.0,
        "max_total_variation": max(tv_values) if tv_values else 0.0,
        "mean_total_variation": float(np.mean(tv_values)) if tv_values else 0.0,
        "parity_max_abs_error": parity_max,
        "generated_low_tokens": len(low_full) - len(prefix),
        "generated_high_tokens": len(high_full) - len(prefix),
        "first_divergence_generated_index": common - len(prefix) if changed else None,
    }


def evaluate(model: MozartTransformer, probes: dict[str, Any], records: dict[str, dict[str, Any]], session: Any | None, *, window_size: int, max_tokens: int) -> dict[str, Any]:
    axes: dict[str, Any] = {}
    for axis, probe in probes["probes"].items():
        tf = _teacher_forced_pair(model, session, probe, records, window_size=window_size)
        ar = _autoregressive_pair(model, session, probe, max_tokens=max_tokens)
        axes[axis] = {
            "low_conditioning": probe["low_conditioning"],
            "high_conditioning": probe["high_conditioning"],
            "teacher_forced": tf,
            "autoregressive": ar,
        }
    return {
        "status": "PASS",
        "semantic_gate": "diagnostic-only",
        "axes": axes,
        "window_size_requested": window_size,
        "max_generated_tokens": max_tokens,
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
    model, _ = _load_model(args.checkpoint, args.config)
    records = _load_records(args.records)
    probes = _load_probes(args.probes)
    session = _load_onnx(args.onnx) if args.onnx is not None else None
    report = evaluate(
        model,
        probes,
        records,
        session,
        window_size=args.window_size,
        max_tokens=args.max_generated_tokens,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
