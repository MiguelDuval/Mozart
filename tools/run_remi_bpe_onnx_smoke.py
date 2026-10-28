#!/usr/bin/env python3
"""Run a bounded autoregressive smoke against an exported REMI/BPE ONNX graph."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import onnxruntime as ort


def select_next_token(
    logits: np.ndarray,
    vocabulary_size: int,
    pad_token_id: int,
    bos_token_id: int,
    eos_token_id: int,
    mask_token_id: int = -1,
) -> int:
    """Mirror Android's REMI/BPE greedy token selection.

    PAD, BOS and MASK are suppressed, EOS remains a valid stopping token, and
    non-finite individual logits are ignored exactly like the Java bridge.
    """
    values = np.asarray(logits)
    if values.ndim != 1 or values.shape[0] != vocabulary_size:
        raise ValueError("REMI/BPE logits do not match the configured vocabulary")
    for label, token_id in (
        ("PAD", pad_token_id),
        ("BOS", bos_token_id),
        ("EOS", eos_token_id),
    ):
        if token_id < 0 or token_id >= vocabulary_size:
            raise ValueError(f"REMI/BPE {label} token ID is outside the vocabulary")
    if len({pad_token_id, bos_token_id, eos_token_id}) != 3:
        raise ValueError("REMI/BPE PAD/BOS/EOS token IDs must be distinct")
    if mask_token_id < -1 or mask_token_id >= vocabulary_size:
        raise ValueError("REMI/BPE MASK token ID is outside the vocabulary")
    if mask_token_id >= 0 and mask_token_id in {pad_token_id, bos_token_id, eos_token_id}:
        raise ValueError("REMI/BPE MASK token ID conflicts with another special token")

    # Java's argmaxRemiBpeToken skips non-finite values and masks these
    # special IDs. Keep EOS available so generation can terminate naturally.
    scores = values.astype(np.float64, copy=True)
    for token_id in (pad_token_id, bos_token_id, mask_token_id):
        if token_id >= 0:
            scores[token_id] = -np.inf
    scores[~np.isfinite(scores)] = -np.inf
    if not np.isfinite(scores).any():
        raise ValueError("REMI/BPE logits have no usable next token")
    return int(np.argmax(scores))


def run_smoke(model_path: Path, manifest_path: Path, output_path: Path, max_new_tokens: int) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime = manifest["runtime"]
    vocab_size = int(manifest["vocabulary_size"])
    context_length = int(manifest["context_length_tokens"])
    bos_id = int(runtime["bos_token_id"])
    eos_id = int(runtime["eos_token_id"])
    pad_id = int(runtime["pad_token_id"])
    mask_id = int(runtime.get("mask_token_id", -1))

    if max_new_tokens < 1 or max_new_tokens > context_length:
        raise ValueError("max-new-tokens must be between 1 and model context length")

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or inputs[0].name != "input_ids" or inputs[0].type != "tensor(int64)":
        raise ValueError("runtime smoke requires one int64 input_ids tensor")
    if len(outputs) != 1 or outputs[0].name != "logits" or outputs[0].type != "tensor(float)":
        raise ValueError("runtime smoke requires one float logits tensor")

    token_ids = [bos_id]
    stopped_at_eos = False
    for _ in range(max_new_tokens):
        window = token_ids[-context_length:]
        input_ids = np.asarray([window], dtype=np.int64)
        logits = session.run(["logits"], {"input_ids": input_ids})[0]
        if logits.shape != (1, vocab_size):
            raise ValueError(f"ONNX logits shape {logits.shape} does not match vocabulary {vocab_size}")
        next_id = select_next_token(
            logits[0],
            vocab_size,
            pad_id,
            bos_id,
            eos_id,
            mask_id,
        )
        if not 0 <= next_id < vocab_size:
            raise ValueError(f"ONNX produced out-of-vocabulary token ID {next_id}")
        token_ids.append(next_id)
        if next_id == eos_id:
            stopped_at_eos = True
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(token_ids, separators=(",", ":")) + "\n", encoding="utf-8")
    return {
        "input_dtype": inputs[0].type,
        "output_dtype": outputs[0].type,
        "vocabulary_size": vocab_size,
        "pad_token_id": pad_id,
        "bos_token_id": bos_id,
        "eos_token_id": eos_id,
        "mask_token_id": mask_id,
        "generated_token_count_including_bos": len(token_ids),
        "stopped_at_eos": stopped_at_eos,
        "token_ids_file": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-token-ids", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=16)
    args = parser.parse_args()
    try:
        report = run_smoke(args.model, args.manifest, args.output_token_ids, args.max_new_tokens)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: REMI/BPE autoregressive smoke failed: {exc}", file=sys.stderr)
        return 1
    print(
        "PASS: REMI/BPE ONNX autoregressive smoke "
        f"vocab={report['vocabulary_size']} "
        f"generated={report['generated_token_count_including_bos']} "
        f"eos={report['stopped_at_eos']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
