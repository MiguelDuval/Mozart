#!/usr/bin/env python3
"""Measure autoregressive sequence responsiveness to Mozart performance controls.

This is a development QA tool. It exercises the same greedy next-token decoding
policy used by the experimental Android ONNX bridge, while keeping model
conditioning explicit in the development model. It never runs on the Android
realtime path and does not freeze the production tensor ABI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from evaluate_mozart_conditioning import (
    DEFAULT_CONDITION_IDS,
    PROBE_INPUT_IDS,
    PERFORMANCE_CONTROL_NAMES,
    _control_tensor,
    _load_onnx_session,
    load_model,
)


EOS = 2
DEFAULT_MAX_GENERATED_TOKENS = 32
DEFAULT_MAX_REPORTED_DIFFS = 16


def _torch_next_logits(
    model: Any,
    input_ids: list[int],
    controls: dict[str, float],
) -> np.ndarray:
    inputs = torch.tensor([input_ids], dtype=torch.long)
    performance_controls = _control_tensor(controls)

    with torch.inference_mode():
        logits = model(
            inputs,
            torch.tensor([DEFAULT_CONDITION_IDS["style_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["substyle_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["mood_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["rhythm_id"]]),
            torch.tensor([DEFAULT_CONDITION_IDS["role_id"]]),
            performance_controls,
        )

    value = (
        logits[0, -1]
        .detach()
        .to(device="cpu", dtype=torch.float32)
        .numpy()
    )
    if value.shape != (512,) or not np.isfinite(value).all():
        raise ValueError("PyTorch next-token logits must be finite [512]")
    return value


def _onnx_next_logits(
    session: Any,
    input_ids: list[int],
    controls: dict[str, float],
) -> np.ndarray:
    outputs = session.run(
        ["logits"],
        {
            "input_ids": np.asarray([input_ids], dtype=np.int64),
            "style_id": np.asarray(
                [DEFAULT_CONDITION_IDS["style_id"]],
                dtype=np.int64,
            ),
            "substyle_id": np.asarray(
                [DEFAULT_CONDITION_IDS["substyle_id"]],
                dtype=np.int64,
            ),
            "mood_id": np.asarray(
                [DEFAULT_CONDITION_IDS["mood_id"]],
                dtype=np.int64,
            ),
            "rhythm_id": np.asarray(
                [DEFAULT_CONDITION_IDS["rhythm_id"]],
                dtype=np.int64,
            ),
            "role_id": np.asarray(
                [DEFAULT_CONDITION_IDS["role_id"]],
                dtype=np.int64,
            ),
            "performance_controls": np.asarray(
                [[float(controls[name]) for name in PERFORMANCE_CONTROL_NAMES]],
                dtype=np.float32,
            ),
        },
    )
    if not outputs:
        raise ValueError("ONNX model returned no logits")
    value = np.asarray(outputs[0])
    if value.ndim != 3 or value.shape[0] != 1 or value.shape[2] != 512:
        raise ValueError(
            f"unexpected ONNX logits shape: {tuple(value.shape)}"
        )
    result = value[0, -1].astype(np.float32, copy=False)
    if not np.isfinite(result).all():
        raise ValueError("ONNX next-token logits must be finite")
    return result


def _greedy_token(logits: np.ndarray) -> int:
    if logits.shape != (512,):
        raise ValueError("greedy logits must have shape [512]")
    return int(np.argmax(logits))


def generate_greedy_torch(
    model: Any,
    controls: dict[str, float],
    *,
    max_generated_tokens: int,
    prefix_tokens: tuple[int, ...] = PROBE_INPUT_IDS,
) -> list[int]:
    if max_generated_tokens < 2:
        raise ValueError("max_generated_tokens must be at least 2")
    if len(prefix_tokens) < 1:
        raise ValueError("prefix_tokens must not be empty")
    if len(prefix_tokens) >= max_generated_tokens:
        raise ValueError("prefix must leave room for generated tokens")

    tokens = [int(token) for token in prefix_tokens]
    while len(tokens) < max_generated_tokens:
        next_token = _greedy_token(
            _torch_next_logits(model, tokens, controls)
        )
        tokens.append(next_token)
        if next_token == EOS:
            break
    return tokens


def generate_greedy_onnx(
    session: Any,
    controls: dict[str, float],
    *,
    max_generated_tokens: int,
    prefix_tokens: tuple[int, ...] = PROBE_INPUT_IDS,
) -> list[int]:
    if max_generated_tokens < 2:
        raise ValueError("max_generated_tokens must be at least 2")
    if len(prefix_tokens) < 1:
        raise ValueError("prefix_tokens must not be empty")
    if len(prefix_tokens) >= max_generated_tokens:
        raise ValueError("prefix must leave room for generated tokens")

    tokens = [int(token) for token in prefix_tokens]
    while len(tokens) < max_generated_tokens:
        next_token = _greedy_token(
            _onnx_next_logits(session, tokens, controls)
        )
        tokens.append(next_token)
        if next_token == EOS:
            break
    return tokens


def compare_token_sequences(
    low_tokens: list[int],
    high_tokens: list[int],
    *,
    max_reported_diffs: int = DEFAULT_MAX_REPORTED_DIFFS,
) -> dict[str, Any]:
    if not low_tokens or not high_tokens:
        raise ValueError("token sequences must not be empty")
    if max_reported_diffs <= 0:
        raise ValueError("max_reported_diffs must be positive")

    common_prefix = 0
    common_limit = min(len(low_tokens), len(high_tokens))
    while (
        common_prefix < common_limit
        and low_tokens[common_prefix] == high_tokens[common_prefix]
    ):
        common_prefix += 1

    differing_positions: list[dict[str, int | None]] = []
    max_index = max(len(low_tokens), len(high_tokens))
    for index in range(common_prefix, max_index):
        low_value = low_tokens[index] if index < len(low_tokens) else None
        high_value = high_tokens[index] if index < len(high_tokens) else None
        if low_value != high_value:
            differing_positions.append(
                {
                    "index": index,
                    "low_token": low_value,
                    "high_token": high_value,
                }
            )
            if len(differing_positions) >= max_reported_diffs:
                break

    return {
        "low_length": len(low_tokens),
        "high_length": len(high_tokens),
        "common_prefix_length": common_prefix,
        "first_divergence_index": (
            common_prefix
            if common_prefix < common_limit
            else None
        ),
        "differing_token_count": sum(
            1
            for index in range(max_index)
            if (low_tokens[index] if index < len(low_tokens) else None)
            != (high_tokens[index] if index < len(high_tokens) else None)
        ),
        "differing_positions": differing_positions,
        "low_ended_with_eos": low_tokens[-1] == EOS,
        "high_ended_with_eos": high_tokens[-1] == EOS,
        "sequence_changed": low_tokens != high_tokens,
    }


def evaluate_sequence_responsiveness(
    model: Any,
    *,
    onnx_session: Any | None = None,
    max_generated_tokens: int = DEFAULT_MAX_GENERATED_TOKENS,
    prefix_tokens: tuple[int, ...] = PROBE_INPUT_IDS,
    require_divergence: bool = True,
    max_reported_diffs: int = DEFAULT_MAX_REPORTED_DIFFS,
) -> dict[str, Any]:
    if max_generated_tokens < 2:
        raise ValueError("max_generated_tokens must be at least 2")
    if len(prefix_tokens) < 1:
        raise ValueError("prefix_tokens must not be empty")
    if len(prefix_tokens) >= max_generated_tokens:
        raise ValueError("prefix must leave room for generated tokens")
    if max_reported_diffs <= 0:
        raise ValueError("max_reported_diffs must be positive")

    baseline = {name: 0.0 for name in PERFORMANCE_CONTROL_NAMES}
    controls_report: dict[str, Any] = {}
    failures: list[str] = []

    for name in PERFORMANCE_CONTROL_NAMES:
        high = dict(baseline)
        high[name] = 1.0

        torch_low = generate_greedy_torch(
            model,
            baseline,
            max_generated_tokens=max_generated_tokens,
            prefix_tokens=prefix_tokens,
        )
        torch_high = generate_greedy_torch(
            model,
            high,
            max_generated_tokens=max_generated_tokens,
            prefix_tokens=prefix_tokens,
        )
        torch_compare = compare_token_sequences(
            torch_low,
            torch_high,
            max_reported_diffs=max_reported_diffs,
        )

        entry: dict[str, Any] = {
            "low_controls": dict(baseline),
            "high_controls": dict(high),
            "torch": {
                **torch_compare,
                "low_tokens": torch_low,
                "high_tokens": torch_high,
            },
        }

        if require_divergence and not torch_compare["sequence_changed"]:
            failures.append(
                f"conditioning control {name} did not change the greedy "
                "generated token sequence"
            )

        if onnx_session is not None:
            onnx_low = generate_greedy_onnx(
                onnx_session,
                baseline,
                max_generated_tokens=max_generated_tokens,
                prefix_tokens=prefix_tokens,
            )
            onnx_high = generate_greedy_onnx(
                onnx_session,
                high,
                max_generated_tokens=max_generated_tokens,
                prefix_tokens=prefix_tokens,
            )
            onnx_compare = compare_token_sequences(
                onnx_low,
                onnx_high,
                max_reported_diffs=max_reported_diffs,
            )
            entry["onnx"] = {
                **onnx_compare,
                "low_tokens": onnx_low,
                "high_tokens": onnx_high,
            }

            low_match = onnx_low == torch_low
            high_match = onnx_high == torch_high
            entry["torch_onnx_sequence_match"] = {
                "low": low_match,
                "high": high_match,
            }
            if not low_match or not high_match:
                failures.append(
                    f"PyTorch/ONNX greedy sequence mismatch for control {name}"
                )

        controls_report[name] = entry

    return {
        "status": "FAIL" if failures else "PASS",
        "require_divergence": require_divergence,
        "max_generated_tokens": max_generated_tokens,
        "prefix_tokens": list(prefix_tokens),
        "controls": controls_report,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--onnx", type=Path)
    parser.add_argument(
        "--max-generated-tokens",
        type=int,
        default=DEFAULT_MAX_GENERATED_TOKENS,
    )
    parser.add_argument(
        "--prefix-tokens",
        type=str,
        default=",".join(str(token) for token in PROBE_INPUT_IDS),
    )
    parser.add_argument(
        "--require-divergence",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--max-reported-diffs",
        type=int,
        default=DEFAULT_MAX_REPORTED_DIFFS,
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.seed < 0:
        raise ValueError("seed must be non-negative")
    try:
        prefix_tokens = tuple(
            int(value.strip())
            for value in args.prefix_tokens.split(",")
            if value.strip()
        )
    except ValueError as exc:
        raise ValueError("prefix-tokens must be a comma-separated integer list") from exc
    if any(token < 0 or token >= 512 for token in prefix_tokens):
        raise ValueError("prefix token ids must be inside the Mozart vocabulary")

    torch.manual_seed(args.seed)

    model, config = load_model(
        args.checkpoint,
        expected_config_path=args.config,
    )
    if args.max_generated_tokens > config.max_sequence_length:
        raise ValueError(
            "max-generated-tokens exceeds checkpoint max_sequence_length"
        )

    onnx_session = (
        _load_onnx_session(args.onnx)
        if args.onnx is not None
        else None
    )
    report = evaluate_sequence_responsiveness(
        model,
        onnx_session=onnx_session,
        max_generated_tokens=args.max_generated_tokens,
        prefix_tokens=prefix_tokens,
        require_divergence=args.require_divergence,
        max_reported_diffs=args.max_reported_diffs,
    )
    report = {
        "model_id": config.model_id,
        "vocabulary_id": config.vocabulary_id,
        "vocabulary_size": config.vocabulary_size,
        "seed": args.seed,
        **report,
    }

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
