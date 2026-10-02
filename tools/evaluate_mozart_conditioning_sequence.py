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


DEFAULT_MAX_GENERATED_TOKENS = 32
DEFAULT_MAX_REPORTED_DIFFS = 16
DEFAULT_LOW_VALUE = 0.1
DEFAULT_HIGH_VALUE = 0.9
DEFAULT_BASE_VALUE = 0.5


PAD = 0
BOS = 1
EOS = 2
CHANNEL_BASE = 16
NOTE_BASE = 32
VELOCITY_BASE = 160
TIME_SHIFT_BASE = 192
DURATION_BASE = 256
CONTROLLER_BASE = 352
CONTROL_VALUE_BASE = 480
VOCABULARY_SIZE = 512


def validate_mozart_token_sequence(
    tokens: list[int],
    *,
    require_eos: bool = True,
) -> dict[str, Any]:
    """Validate a complete token stream or an open-ended generation prefix.

    When require_eos is False, the final event may be incomplete because the
    evaluator is validating a bounded autoregressive prefix rather than claiming
    that generation has finished. Malformed token ordering is still rejected.
    """
    minimum = 2 if require_eos else 1
    if len(tokens) < minimum:
        return {
            "valid": False,
            "error": "token sequence is shorter than the required minimum",
        }
    if tokens[0] != BOS:
        return {
            "valid": False,
            "index": 0,
            "token": tokens[0],
            "error": "token sequence must start with BOS",
        }

    eos_present = bool(tokens and tokens[-1] == EOS)
    if require_eos and not eos_present:
        return {
            "valid": False,
            "index": len(tokens) - 1,
            "token": tokens[-1],
            "error": "token sequence must end with EOS",
        }
    if eos_present and len(tokens) == 1:
        return {
            "valid": False,
            "index": 0,
            "token": tokens[0],
            "error": "token sequence cannot be only BOS/EOS",
        }

    stream_end = len(tokens) - 1 if eos_present else len(tokens)
    channel_initialized = False
    index = 1

    while index < stream_end:
        token = tokens[index]
        if not 0 <= token < VOCABULARY_SIZE:
            return {
                "valid": False,
                "index": index,
                "token": token,
                "error": "token id is outside the Mozart vocabulary",
            }
        if token in (PAD, BOS, EOS):
            return {
                "valid": False,
                "index": index,
                "token": token,
                "error": "special token is not allowed inside the stream",
            }

        if CHANNEL_BASE <= token < NOTE_BASE:
            channel_initialized = True
            index += 1
            continue

        if TIME_SHIFT_BASE <= token < DURATION_BASE:
            index += 1
            continue

        if not channel_initialized:
            return {
                "valid": False,
                "index": index,
                "token": token,
                "error": "event token appears before a channel token",
            }

        if NOTE_BASE <= token < VELOCITY_BASE:
            remaining = stream_end - index
            if remaining == 1 and not require_eos:
                return {"valid": True, "error": None, "complete": False}
            velocity = tokens[index + 1]
            if not VELOCITY_BASE <= velocity < TIME_SHIFT_BASE:
                return {
                    "valid": False,
                    "index": index + 1,
                    "token": velocity,
                    "error": "note token is not followed by a velocity token",
                }
            if remaining == 2 and not require_eos:
                return {"valid": True, "error": None, "complete": False}
            duration = tokens[index + 2]
            if not DURATION_BASE <= duration < CONTROLLER_BASE:
                return {
                    "valid": False,
                    "index": index + 2,
                    "token": duration,
                    "error": "note velocity is not followed by a duration token",
                }
            index += 3
            continue

        if CONTROLLER_BASE <= token < CONTROL_VALUE_BASE:
            remaining = stream_end - index
            if remaining == 1 and not require_eos:
                return {"valid": True, "error": None, "complete": False}
            value = tokens[index + 1]
            if not CONTROL_VALUE_BASE <= value < VOCABULARY_SIZE:
                return {
                    "valid": False,
                    "index": index + 1,
                    "token": value,
                    "error": "controller token is not followed by a control-value token",
                }
            index += 2
            continue

        if CONTROL_VALUE_BASE <= token < VOCABULARY_SIZE:
            return {
                "valid": False,
                "index": index,
                "token": token,
                "error": "control-value token appears without a controller token",
            }

        return {
            "valid": False,
            "index": index,
            "token": token,
            "error": "unknown Mozart token range",
        }

    return {
        "valid": True,
        "error": None,
        "complete": eos_present,
    }


def load_sequence_probe_file(path: Path) -> dict[str, tuple[int, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read sequence probe file {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("sequence probe file root must be an object")
    if payload.get("status") != "synthetic-conditioning-sequence-probes":
        raise ValueError("unsupported sequence probe file status")

    controls = payload.get("controls")
    if not isinstance(controls, dict):
        raise ValueError("sequence probe file controls must be an object")

    result: dict[str, tuple[int, ...]] = {}
    for name in PERFORMANCE_CONTROL_NAMES:
        entry = controls.get(name)
        if not isinstance(entry, dict):
            raise ValueError(f"missing sequence probe for control {name}")
        raw_tokens = entry.get("prefix_tokens")
        if not isinstance(raw_tokens, list) or not raw_tokens:
            raise ValueError(
                f"sequence probe {name} must contain non-empty prefix_tokens"
            )
        try:
            prefix = tuple(int(token) for token in raw_tokens)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"sequence probe {name} prefix_tokens must be integers"
            ) from exc
        if any(token < 0 or token >= 512 for token in prefix):
            raise ValueError(
                f"sequence probe {name} prefix token ids must be in the Mozart vocabulary"
            )
        if prefix[0] != 1:
            raise ValueError(
                f"sequence probe {name} must start with BOS token 1"
            )
        if prefix[-1] == EOS:
            raise ValueError(
                f"sequence probe {name} must stop before EOS"
            )
        grammar = validate_mozart_token_sequence(
            list(prefix),
            require_eos=False,
        )
        if not grammar["valid"]:
            raise ValueError(
                f"sequence probe {name} is not a valid MIDI grammar prefix: "
                f"{grammar['error']}"
            )
        declared_length = entry.get("prefix_length")
        if declared_length != len(prefix):
            raise ValueError(
                f"sequence probe {name} prefix_length does not match prefix_tokens"
            )
        divergence_index = entry.get("first_target_divergence_index")
        if divergence_index != len(prefix):
            raise ValueError(
                f"sequence probe {name} divergence index must equal prefix length"
            )
        result[name] = prefix

    return result


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


def _has_channel_token(tokens: list[int]) -> bool:
    return any(
        CHANNEL_BASE <= token < NOTE_BASE
        for token in tokens
    )


def is_allowed_next_token(tokens: list[int], next_token: int) -> bool:
    """Return whether a token is valid at the current Mozart grammar state."""
    if not tokens or not 0 <= next_token < VOCABULARY_SIZE:
        return False

    last = tokens[-1]
    if last == BOS:
        return CHANNEL_BASE <= next_token < NOTE_BASE or (
            TIME_SHIFT_BASE <= next_token < DURATION_BASE
        )
    if NOTE_BASE <= last < VELOCITY_BASE:
        return VELOCITY_BASE <= next_token < TIME_SHIFT_BASE
    if VELOCITY_BASE <= last < TIME_SHIFT_BASE:
        return DURATION_BASE <= next_token < CONTROLLER_BASE
    if CONTROLLER_BASE <= last < CONTROL_VALUE_BASE:
        return CONTROL_VALUE_BASE <= next_token < VOCABULARY_SIZE
    if DURATION_BASE <= last < CONTROLLER_BASE or (
        CONTROL_VALUE_BASE <= last < VOCABULARY_SIZE
    ):
        return (
            next_token == EOS
            or CHANNEL_BASE <= next_token < NOTE_BASE
            or TIME_SHIFT_BASE <= next_token < DURATION_BASE
            or NOTE_BASE <= next_token < VELOCITY_BASE
            or CONTROLLER_BASE <= next_token < CONTROL_VALUE_BASE
        )
    if TIME_SHIFT_BASE <= last < DURATION_BASE:
        return (
            CHANNEL_BASE <= next_token < NOTE_BASE
            or TIME_SHIFT_BASE <= next_token < DURATION_BASE
            or (
                _has_channel_token(tokens)
                and (
                    NOTE_BASE <= next_token < VELOCITY_BASE
                    or CONTROLLER_BASE <= next_token < CONTROL_VALUE_BASE
                )
            )
        )
    if CHANNEL_BASE <= last < NOTE_BASE:
        return (
            NOTE_BASE <= next_token < VELOCITY_BASE
            or CONTROLLER_BASE <= next_token < CONTROL_VALUE_BASE
        )
    return False


def _grammar_allowed_mask(tokens: list[int]) -> np.ndarray:
    mask = np.zeros(VOCABULARY_SIZE, dtype=bool)
    for token in range(VOCABULARY_SIZE):
        mask[token] = is_allowed_next_token(tokens, token)
    if not np.any(mask):
        raise ValueError("Mozart grammar has no valid next token")
    return mask


def _greedy_token(
    logits: np.ndarray,
    *,
    allowed_mask: np.ndarray | None = None,
) -> int:
    if logits.shape != (512,):
        raise ValueError("greedy logits must have shape [512]")
    if not np.isfinite(logits).all():
        raise ValueError("greedy logits must be finite")
    if allowed_mask is None:
        return int(np.argmax(logits))
    if allowed_mask.shape != (512,) or allowed_mask.dtype != bool:
        raise ValueError("allowed token mask must have shape [512] and bool dtype")
    if not np.any(allowed_mask):
        raise ValueError("allowed token mask must contain at least one token")
    masked = np.where(allowed_mask, logits, -np.inf)
    return int(np.argmax(masked))


def generate_greedy_torch(
    model: Any,
    controls: dict[str, float],
    *,
    max_generated_tokens: int,
    prefix_tokens: tuple[int, ...] = (1, 16, 68, 185),
    grammar_constrained: bool = False,
) -> list[int]:
    if max_generated_tokens < 2:
        raise ValueError("max_generated_tokens must be at least 2")
    if len(prefix_tokens) < 1:
        raise ValueError("prefix_tokens must not be empty")
    if len(prefix_tokens) >= max_generated_tokens:
        raise ValueError("prefix must leave room for generated tokens")

    tokens = [int(token) for token in prefix_tokens]
    while len(tokens) < max_generated_tokens:
        logits = _torch_next_logits(model, tokens, controls)
        next_token = _greedy_token(
            logits,
            allowed_mask=(
                _grammar_allowed_mask(tokens)
                if grammar_constrained
                else None
            ),
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
    prefix_tokens: tuple[int, ...] = (1, 16, 68, 185),
    grammar_constrained: bool = False,
) -> list[int]:
    if max_generated_tokens < 2:
        raise ValueError("max_generated_tokens must be at least 2")
    if len(prefix_tokens) < 1:
        raise ValueError("prefix_tokens must not be empty")
    if len(prefix_tokens) >= max_generated_tokens:
        raise ValueError("prefix must leave room for generated tokens")

    tokens = [int(token) for token in prefix_tokens]
    while len(tokens) < max_generated_tokens:
        logits = _onnx_next_logits(session, tokens, controls)
        next_token = _greedy_token(
            logits,
            allowed_mask=(
                _grammar_allowed_mask(tokens)
                if grammar_constrained
                else None
            ),
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
    prefix_tokens: tuple[int, ...] = (1, 16, 68, 185),
    prefix_tokens_by_control: dict[str, tuple[int, ...]] | None = None,
    require_divergence: bool = True,
    require_valid_grammar: bool = False,
    max_reported_diffs: int = DEFAULT_MAX_REPORTED_DIFFS,
    low_value: float = DEFAULT_LOW_VALUE,
    high_value: float = DEFAULT_HIGH_VALUE,
    base_value: float = DEFAULT_BASE_VALUE,
    grammar_constrained: bool = False,
) -> dict[str, Any]:
    if max_generated_tokens < 2:
        raise ValueError("max_generated_tokens must be at least 2")
    if len(prefix_tokens) < 1:
        raise ValueError("prefix_tokens must not be empty")
    if len(prefix_tokens) >= max_generated_tokens:
        raise ValueError("prefix must leave room for generated tokens")
    if max_reported_diffs <= 0:
        raise ValueError("max_reported_diffs must be positive")
    if not 0.0 <= low_value < high_value <= 1.0:
        raise ValueError("low-value and high-value must satisfy 0 <= low < high <= 1")
    if not 0.0 <= base_value <= 1.0:
        raise ValueError("base-value must be in [0, 1]")

    baseline = {name: base_value for name in PERFORMANCE_CONTROL_NAMES}
    controls_report: dict[str, Any] = {}
    failures: list[str] = []

    for name in PERFORMANCE_CONTROL_NAMES:
        control_prefix = (
            prefix_tokens_by_control.get(name, prefix_tokens)
            if prefix_tokens_by_control is not None
            else prefix_tokens
        )
        if len(control_prefix) >= max_generated_tokens:
            raise ValueError(
                f"conditioning control {name} prefix leaves no generation budget"
            )

        low = dict(baseline)
        low[name] = low_value
        high = dict(baseline)
        high[name] = high_value

        torch_low = generate_greedy_torch(
            model,
            low,
            max_generated_tokens=max_generated_tokens,
            prefix_tokens=control_prefix,
            grammar_constrained=grammar_constrained,
        )
        torch_high = generate_greedy_torch(
            model,
            high,
            max_generated_tokens=max_generated_tokens,
            prefix_tokens=control_prefix,
            grammar_constrained=grammar_constrained,
        )
        torch_compare = compare_token_sequences(
            torch_low,
            torch_high,
            max_reported_diffs=max_reported_diffs,
        )
        torch_low_grammar = validate_mozart_token_sequence(torch_low, require_eos=False)
        torch_high_grammar = validate_mozart_token_sequence(torch_high, require_eos=False)
        if require_valid_grammar:
            for label, grammar in (
                ("low", torch_low_grammar),
                ("high", torch_high_grammar),
            ):
                if not grammar["valid"]:
                    failures.append(
                        f"conditioning control {name} produced invalid greedy "
                        f"PyTorch {label} token sequence: {grammar['error']}"
                    )

        entry: dict[str, Any] = {
            "prefix_tokens": list(control_prefix),
            "prefix_length": len(control_prefix),
            "low_controls": dict(low),
            "high_controls": dict(high),
            "torch": {
                **torch_compare,
                "low_tokens": torch_low,
                "high_tokens": torch_high,
                "low_grammar": torch_low_grammar,
                "high_grammar": torch_high_grammar,
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
                low,
                max_generated_tokens=max_generated_tokens,
                prefix_tokens=control_prefix,
                grammar_constrained=grammar_constrained,
            )
            onnx_high = generate_greedy_onnx(
                onnx_session,
                high,
                max_generated_tokens=max_generated_tokens,
                prefix_tokens=control_prefix,
                grammar_constrained=grammar_constrained,
            )
            onnx_compare = compare_token_sequences(
                onnx_low,
                onnx_high,
                max_reported_diffs=max_reported_diffs,
            )
            onnx_low_grammar = validate_mozart_token_sequence(onnx_low, require_eos=False)
            onnx_high_grammar = validate_mozart_token_sequence(onnx_high, require_eos=False)
            if require_valid_grammar:
                for label, grammar in (
                    ("low", onnx_low_grammar),
                    ("high", onnx_high_grammar),
                ):
                    if not grammar["valid"]:
                        failures.append(
                            f"conditioning control {name} produced invalid greedy "
                            f"ONNX {label} token sequence: {grammar['error']}"
                        )
            entry["onnx"] = {
                **onnx_compare,
                "low_tokens": onnx_low,
                "high_tokens": onnx_high,
                "low_grammar": onnx_low_grammar,
                "high_grammar": onnx_high_grammar,
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
        "require_valid_grammar": require_valid_grammar,
        "grammar_constrained": grammar_constrained,
        "max_generated_tokens": max_generated_tokens,
        "control_probe_values": {
            "low": low_value,
            "high": high_value,
            "base_other_controls": base_value,
        },
        "prefix_tokens": list(prefix_tokens),
        "prefix_tokens_by_control": (
            {
                name: list(value)
                for name, value in prefix_tokens_by_control.items()
            }
            if prefix_tokens_by_control is not None
            else None
        ),
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
        default="1,16,68,185",
    )
    parser.add_argument(
        "--probe-file",
        type=Path,
        help="Use fixture-derived control-specific greedy probe prefixes.",
    )
    parser.add_argument(
        "--require-divergence",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--require-valid-grammar",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require every generated PyTorch/ONNX sequence to be decoder-valid.",
    )
        parser.add_argument(
        "--grammar-constrained",
        action="store_true",
        help="Mask greedy logits to tokens valid for the current Mozart grammar state.",
    )
    parser.add_argument(
        "--max-reported-diffs",
        type=int,
        default=DEFAULT_MAX_REPORTED_DIFFS,
    )
    parser.add_argument("--low-value", type=float, default=DEFAULT_LOW_VALUE)
    parser.add_argument("--high-value", type=float, default=DEFAULT_HIGH_VALUE)
    parser.add_argument("--base-value", type=float, default=DEFAULT_BASE_VALUE)
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

    prefix_tokens_by_control = (
        load_sequence_probe_file(args.probe_file)
        if args.probe_file is not None
        else None
    )

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
        prefix_tokens_by_control=prefix_tokens_by_control,
        require_divergence=args.require_divergence,
        require_valid_grammar=args.require_valid_grammar,
        grammar_constrained=args.grammar_constrained,
        max_reported_diffs=args.max_reported_diffs,
        low_value=args.low_value,
        high_value=args.high_value,
        base_value=args.base_value,
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
