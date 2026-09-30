#!/usr/bin/env python3
"""Inspect and validate the actual ONNX tensor ABI of a Mozart model artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import onnx
from onnx import TensorProto


EXPECTED_INPUTS = (
    ("input_ids", "int64", 2),
    ("style_id", "int64", 1),
    ("substyle_id", "int64", 1),
    ("mood_id", "int64", 1),
    ("rhythm_id", "int64", 1),
    ("role_id", "int64", 1),
)


def dtype_name(value: int) -> str:
    names = {
        TensorProto.INT64: "int64",
        TensorProto.FLOAT: "float32",
    }
    try:
        return names[value]
    except KeyError as exc:
        raise ValueError(f"unsupported ONNX tensor dtype enum: {value}") from exc


def tensor_shape(value_info: onnx.ValueInfoProto) -> list[str | int]:
    dims: list[str | int] = []
    for dim in value_info.type.tensor_type.shape.dim:
        if dim.dim_param:
            dims.append(dim.dim_param)
        elif dim.HasField("dim_value"):
            dims.append(dim.dim_value)
        else:
            dims.append("?")
    return dims


def tensor_dtype(value_info: onnx.ValueInfoProto) -> str:
    return dtype_name(value_info.type.tensor_type.elem_type)


def canonical_shape(
    name: str,
    shape: list[str | int],
    *,
    batch_symbol: str | None = None,
    sequence_symbol: str | None = None,
) -> list[str | int]:
    if name == "input_ids":
        if len(shape) != 2:
            raise ValueError("input_ids must have rank 2")
        return [shape[0], "sequence"]

    if len(shape) == 1 and shape[0] == 1:
        return [1]

    if (
        len(shape) == 3
        and shape[0] == 1
        and shape[1] == sequence_symbol
    ):
        return [1, "sequence", shape[2]]

    return shape


def inspect_model(path: Path, model_id: str) -> dict:
    model = onnx.load(path, load_external_data=True)
    onnx.checker.check_model(model)

    input_infos = list(model.graph.input)
    output_infos = list(model.graph.output)
    input_names = [value.name for value in input_infos]
    output_names = [value.name for value in output_infos]

    if input_names != [item[0] for item in EXPECTED_INPUTS]:
        raise ValueError(
            "unexpected input names: "
            f"{input_names!r}; expected {[item[0] for item in EXPECTED_INPUTS]!r}"
        )
    if output_names != ["logits"]:
        raise ValueError(
            f"unexpected output names: {output_names!r}; expected ['logits']"
        )

    first_shape = tensor_shape(input_infos[0])
    if len(first_shape) != 2:
        raise ValueError(f"input_ids must have rank 2, got {first_shape!r}")

    if first_shape[0] != 1:
        raise ValueError(
            f"input_ids batch dimension must be fixed to 1, got {first_shape[0]!r}"
        )
    sequence_symbol = first_shape[1] if isinstance(first_shape[1], str) else None
    if sequence_symbol is None:
        raise ValueError("input_ids sequence dimension must be symbolic")

    inputs = []
    for value_info, (name, expected_dtype, expected_rank) in zip(
        input_infos,
        EXPECTED_INPUTS,
        strict=True,
    ):
        dtype = tensor_dtype(value_info)
        shape = tensor_shape(value_info)
        if dtype != expected_dtype:
            raise ValueError(
                f"{name} dtype mismatch: {dtype!r} != {expected_dtype!r}"
            )
        if len(shape) != expected_rank:
            raise ValueError(
                f"{name} rank mismatch: {len(shape)} != {expected_rank}"
            )
        canonical = canonical_shape(
            name,
            shape,
            batch_symbol=1,
            sequence_symbol=sequence_symbol,
        )
        if name != "input_ids" and canonical != [1]:
            raise ValueError(
                f"{name} first dimension must be fixed to 1: {shape!r}"
            )
        inputs.append({
            "name": name,
            "dtype": dtype,
            "shape": canonical,
        })

    output = output_infos[0]
    output_dtype = tensor_dtype(output)
    output_shape = tensor_shape(output)
    canonical_output = canonical_shape(
        "logits",
        output_shape,
        batch_symbol=1,
        sequence_symbol=sequence_symbol,
    )
    if output_dtype != "float32":
        raise ValueError(
            f"logits dtype mismatch: {output_dtype!r} != 'float32'"
        )
    if canonical_output != ["batch", "sequence", 512]:
        raise ValueError(
            "logits shape mismatch: "
            f"{canonical_output!r} != ['batch', 'sequence', 512]"
        )

    opsets = [
        {
            "domain": opset.domain,
            "version": opset.version,
        }
        for opset in model.opset_import
    ]

    return {
        "model_id": model_id,
        "format": "onnx",
        "inputs": inputs,
        "outputs": [
            {
                "name": "logits",
                "dtype": output_dtype,
                "shape": canonical_output,
            }
        ],
        "opsets": opsets,
        "vocabulary_size": 512,
        "context_symbolic": {
            "batch": 1,
            "sequence": sequence_symbol,
        },
        "file_sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        "file_size_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("docs/model-training-config.json"),
    )
    args = parser.parse_args()

    payload = json.loads(args.config.read_text(encoding="utf-8"))
    model_id = payload["model_id"]
    try:
        report = inspect_model(args.model, model_id)
    except (OSError, ValueError, onnx.checker.ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
