#!/usr/bin/env python3
"""Create a tiny external-vocabulary ONNX fixture for the Android Java bridge smoke."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

VOCAB_SIZE = 20_000
PAD_ID = 0
BOS_ID = 1
EOS_ID = 2
CONTEXT_LENGTH = 16
MAX_GENERATED_TOKENS = 8


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_model(path: Path) -> None:
    # Shape/Gather/Cast/Mul ensures input_ids remains a required input, while
    # multiplying the resulting dimension by zero leaves the logits constant.
    logits = np.full((1, VOCAB_SIZE), -50.0, dtype=np.float32)
    logits[0, PAD_ID] = 20.0
    logits[0, BOS_ID] = 19.0
    logits[0, EOS_ID] = 100.0
    base_logits = numpy_helper.from_array(logits, name="base_logits")
    batch_index = numpy_helper.from_array(np.asarray([0], dtype=np.int64), name="batch_index")
    zero = numpy_helper.from_array(np.asarray([0.0], dtype=np.float32), name="zero")

    input_ids = helper.make_tensor_value_info(
        "input_ids", TensorProto.INT64, [1, "sequence_length"]
    )
    output_logits = helper.make_tensor_value_info(
        "logits", TensorProto.FLOAT, [1, VOCAB_SIZE]
    )
    nodes = [
        helper.make_node("Shape", ["input_ids"], ["input_shape"]),
        helper.make_node("Gather", ["input_shape", "batch_index"], ["batch_dim"], axis=0),
        helper.make_node("Cast", ["batch_dim"], ["batch_dim_float"], to=TensorProto.FLOAT),
        helper.make_node("Mul", ["batch_dim_float", "zero"], ["zero_dependency"]),
        helper.make_node("Add", ["base_logits", "zero_dependency"], ["logits"]),
    ]
    graph = helper.make_graph(
        nodes,
        "mozart_android_remi_bpe_bridge_smoke",
        [input_ids],
        [output_logits],
        [base_logits, batch_index, zero],
    )
    model = helper.make_model(
        graph,
        producer_name="Mozart Android REMI/BPE bridge smoke",
        opset_imports=[helper.make_opsetid("", 17)],
    )
    model.ir_version = min(onnx.IR_VERSION, 10)
    onnx.checker.check_model(model)
    path.write_bytes(model.SerializeToString())


def create_fixture(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.onnx"
    tokenizer_path = output_dir / "tokenizer-fixture.json"
    manifest_path = output_dir / "manifest.json"

    create_model(model_path)
    # This is deliberately a placeholder: Android's Java bridge verifies its
    # SHA-256, while the separate real-model workflow validates the real tokenizer.
    tokenizer_path.write_text(
        json.dumps(
            {
                "fixture_only": True,
                "purpose": "android_onnx_runtime_abi_smoke_not_a_real_miditok_tokenizer",
                "vocabulary_size": VOCAB_SIZE,
                "special_token_ids": {"pad": PAD_ID, "bos": BOS_ID, "eos": EOS_ID},
            },
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "manifest_schema_version": 1,
        "manifest_status": "frozen",
        "model_id": "android-remi-bpe-runtime-smoke-fixture",
        "model_format": "onnx",
        "model_file": model_path.name,
        "model_sha256": sha256_file(model_path),
        "vocabulary_id": "miditok-remi-bpe-v1",
        "vocabulary_size": VOCAB_SIZE,
        "context_length_tokens": CONTEXT_LENGTH,
        "max_generated_tokens": MAX_GENERATED_TOKENS,
        "inputs": [
            {"name": "input_ids", "dtype": "int64", "shape": [1, -1]}
        ],
        "outputs": [
            {"name": "logits", "dtype": "float32", "shape": [1, VOCAB_SIZE]}
        ],
        "runtime": {
            "backend": "onnxruntime",
            "token_mode": "remi_bpe",
            "external_vocabulary_size": VOCAB_SIZE,
            "input_dtype": "int64",
            "input_name": "input_ids",
            "output_name": "logits",
            "context_length_tokens": CONTEXT_LENGTH,
            "max_generated_tokens": MAX_GENERATED_TOKENS,
            "pad_token_id": PAD_ID,
            "bos_token_id": BOS_ID,
            "eos_token_id": EOS_ID,
            "tokenizer_file": tokenizer_path.name,
            "tokenizer_sha256": sha256_file(tokenizer_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "model": str(model_path),
        "model_sha256": manifest["model_sha256"],
        "tokenizer": str(tokenizer_path),
        "tokenizer_sha256": manifest["runtime"]["tokenizer_sha256"],
        "manifest": str(manifest_path),
        "vocabulary_size": VOCAB_SIZE,
        "expected_tokens": [BOS_ID, EOS_ID],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = create_fixture(args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
