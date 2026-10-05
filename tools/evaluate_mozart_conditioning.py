#!/usr/bin/env python3
"""Measure development-model responsiveness to Mozart performance controls.

This is a development QA tool. It does not define or freeze a production
tensor ABI and never runs on the Android realtime path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from mozart_conditioning import PERFORMANCE_CONTROL_NAMES
from mozart_model import ModelConfig, MozartTransformer


PROBE_INPUT_IDS = (1, 16, 92)  # BOS, channel 0, MIDI note 60.
DEFAULT_CONDITION_IDS = {
    "style_id": 0,
    "substyle_id": 0,
    "mood_id": 0,
    "rhythm_id": 0,
    "role_id": 0,
}


def _config_from_checkpoint(payload: dict[str, Any]) -> ModelConfig:
    raw = payload.get("config")
    if not isinstance(raw, dict):
        raise ValueError("checkpoint does not contain a model config")

    config = dict(raw)
    names = config.get("performance_control_names")
    if isinstance(names, list):
        config["performance_control_names"] = tuple(names)
    elif not isinstance(names, tuple):
        raise ValueError("checkpoint performance control schema is missing")

    return ModelConfig(**config)


def load_model(
    checkpoint_path: Path,
    expected_config_path: Path | None = None,
) -> tuple[MozartTransformer, ModelConfig]:
    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=False,
    )
    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint payload is not an object")

    config = _config_from_checkpoint(checkpoint)
    if config.vocabulary_id != "mozart-midi-events-v1":
        raise ValueError(
            f"unsupported vocabulary id: {config.vocabulary_id!r}"
        )
    if config.vocabulary_size != 512:
        raise ValueError(
            f"unsupported vocabulary size: {config.vocabulary_size}"
        )
    if tuple(config.performance_control_names) != tuple(
        PERFORMANCE_CONTROL_NAMES
    ):
        raise ValueError("unsupported performance control schema")

    if expected_config_path is not None:
        expected = ModelConfig.from_json(expected_config_path)
        if expected.vocabulary_id != config.vocabulary_id:
            raise ValueError("checkpoint vocabulary id differs from expected config")
        if expected.vocabulary_size != config.vocabulary_size:
            raise ValueError("checkpoint vocabulary size differs from expected config")
        if tuple(expected.performance_control_names) != tuple(
            config.performance_control_names
        ):
            raise ValueError(
                "checkpoint performance control schema differs from expected config"
            )

    state = checkpoint.get("model_state")
    if not isinstance(state, dict):
        raise ValueError("checkpoint does not contain model_state")

    model = MozartTransformer(config)
    model.load_state_dict(state)
    model.eval()
    return model, config


def _control_tensor(
    values: dict[str, float],
) -> torch.Tensor:
    ordered = [float(values[name]) for name in PERFORMANCE_CONTROL_NAMES]
    if any(not 0.0 <= value <= 1.0 for value in ordered):
        raise ValueError("probe controls must be in [0, 1]")
    return torch.tensor([ordered], dtype=torch.float32)


def _torch_logits(
    model: MozartTransformer,
    controls: dict[str, float],
) -> np.ndarray:
    input_ids = torch.tensor([PROBE_INPUT_IDS], dtype=torch.long)
    performance_controls = _control_tensor(controls)

    with torch.inference_mode():
        logits = model(
            input_ids,
            torch.tensor([DEFAULT_CONDITION_IDS["style_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["substyle_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["mood_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["rhythm_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["role_id"]]),
            performance_controls,
        )

    return (
        logits[0, -1]
        .detach()
        .to(device="cpu", dtype=torch.float32)
        .numpy()
    )


def _onnx_logits(
    session: Any,
    controls: dict[str, float],
) -> np.ndarray:
    input_ids = np.asarray([PROBE_INPUT_IDS], dtype=np.int64)
    performance_controls = np.asarray(
        [[float(controls[name]) for name in PERFORMANCE_CONTROL_NAMES]],
        dtype=np.float32,
    )
    outputs = session.run(
        ["logits"],
        {
            "input_ids": input_ids,
            "style_id": np.asarray([DEFAULT_CONDITION_IDS["style_id"]], dtype=np.int64),
            "substyle_id": np.asarray(
                [DEFAULT_CONDITION_IDS["substyle_id"]], dtype=np.int64
            ),
            "mood_id": np.asarray([DEFAULT_CONDITION_IDS["mood_id"]], dtype=np.int64),
            "rhythm_id": np.asarray(
                [DEFAULT_CONDITION_IDS["rhythm_id"]], dtype=np.int64
            ),
            "role_id": np.asarray([DEFAULT_CONDITION_IDS["role_id"]], dtype=np.int64),
            "performance_controls": performance_controls,
        },
    )
    if not outputs:
        raise ValueError("ONNX model returned no outputs")

    value = np.asarray(outputs[0])
    if value.ndim != 3 or value.shape[0] != 1 or value.shape[2] != 512:
        raise ValueError(
            f"unexpected ONNX logits shape: {tuple(value.shape)}"
        )
    return value[0, -1].astype(np.float32, copy=False)


def _measure_pair(
    low: np.ndarray,
    high: np.ndarray,
) -> dict[str, Any]:
    if low.shape != (512,) or high.shape != (512,):
        raise ValueError("logits must have shape [512]")
    if not np.isfinite(low).all() or not np.isfinite(high).all():
        raise ValueError("logits contain non-finite values")

    delta = np.abs(high - low)
    low_top1 = int(np.argmax(low))
    high_top1 = int(np.argmax(high))
    return {
        "low_value": 0.0,
        "high_value": 1.0,
        "max_abs_delta": float(np.max(delta)),
        "mean_abs_delta": float(np.mean(delta)),
        "low_top1": low_top1,
        "high_top1": high_top1,
        "top1_changed": low_top1 != high_top1,
    }


def evaluate_conditioning_responsiveness(
    model: MozartTransformer,
    *,
    onnx_session: Any | None = None,
    min_delta: float = 1.0e-8,
    parity_tolerance: float = 5.0e-4,
) -> dict[str, Any]:
    if min_delta <= 0.0:
        raise ValueError("min_delta must be positive")
    if parity_tolerance <= 0.0:
        raise ValueError("parity_tolerance must be positive")

    baseline = {name: 0.0 for name in PERFORMANCE_CONTROL_NAMES}
    controls: dict[str, dict[str, Any]] = {}
    max_parity_error = 0.0

    for name in PERFORMANCE_CONTROL_NAMES:
        high = dict(baseline)
        high[name] = 1.0

        torch_low = _torch_logits(model, baseline)
        torch_high = _torch_logits(model, high)
        result = _measure_pair(torch_low, torch_high)

        if result["max_abs_delta"] <= min_delta:
            raise RuntimeError(
                f"conditioning control {name} produced no measurable "
                f"PyTorch logit response: {result['max_abs_delta']:.9g}"
            )

        if onnx_session is not None:
            onnx_low = _onnx_logits(onnx_session, baseline)
            onnx_high = _onnx_logits(onnx_session, high)
            onnx_result = _measure_pair(onnx_low, onnx_high)
            parity_low = float(np.max(np.abs(torch_low - onnx_low)))
            parity_high = float(np.max(np.abs(torch_high - onnx_high)))
            parity_error = max(parity_low, parity_high)
            max_parity_error = max(max_parity_error, parity_error)

            if onnx_result["max_abs_delta"] <= min_delta:
                raise RuntimeError(
                    f"conditioning control {name} produced no measurable "
                    f"ONNX logit response: "
                    f"{onnx_result['max_abs_delta']:.9g}"
                )
            if parity_error > parity_tolerance:
                raise RuntimeError(
                    f"PyTorch/ONNX parity exceeded tolerance for {name}: "
                    f"{parity_error:.9g} > {parity_tolerance:.9g}"
                )

            result["onnx"] = {
                **onnx_result,
                "torch_onnx_max_abs_error": parity_error,
            }

        controls[name] = result

    return {
        "status": "PASS",
        "controls": controls,
        "onnx_max_abs_error": max_parity_error if onnx_session is not None else None,
        "probe_input_ids": list(PROBE_INPUT_IDS),
        "probe_low": 0.0,
        "probe_high": 1.0,
    }


def _load_onnx_session(path: Path) -> Any:
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError(
            "onnxruntime is required when --onnx is supplied"
        ) from exc

    return ort.InferenceSession(
        str(path),
        providers=["CPUExecutionProvider"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--onnx", type=Path)
    parser.add_argument("--min-delta", type=float, default=1.0e-8)
    parser.add_argument("--parity-tolerance", type=float, default=5.0e-4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    model, config = load_model(
        args.checkpoint,
        expected_config_path=args.config,
    )
    onnx_session = (
        _load_onnx_session(args.onnx)
        if args.onnx is not None
        else None
    )
    report = evaluate_conditioning_responsiveness(
        model,
        onnx_session=onnx_session,
        min_delta=args.min_delta,
        parity_tolerance=args.parity_tolerance,
    )
    report = {
        "model_id": config.model_id,
        "vocabulary_id": config.vocabulary_id,
        "vocabulary_size": config.vocabulary_size,
        **report,
    }

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
