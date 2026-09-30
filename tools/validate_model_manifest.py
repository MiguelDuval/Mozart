#!/usr/bin/env python3
"""Validate the machine-readable Mozart model manifest contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
ALLOWED_STATUS = {"template", "frozen"}
ALLOWED_DISTRIBUTION = {"commercial", "private_experimental"}
REQUIRED_ROOT_FIELDS = (
    "manifest_schema_version", "model_id", "model_revision", "model_file",
    "model_format", "model_sha256", "distribution_class", "vocabulary_id",
    "vocabulary_size", "context_length_tokens", "max_generated_tokens",
    "inputs", "outputs", "kv_cache", "quantization", "conditioning",
    "decoding", "provenance", "licenses",
)
REQUIRED_TENSOR_FIELDS = ("name", "dtype", "shape", "layout", "role")
REQUIRED_CONDITIONING_FIELDS = (
    "style_family", "substyle", "mood", "rhythm", "role", "key_scale",
    "chords", "density", "energy", "syncopation", "swing", "variation", "seed",
)
REQUIRED_DECODING_FIELDS = ("strategy", "temperature", "top_k", "top_p", "seed_policy")
REQUIRED_PROVENANCE_FIELDS = ("training_source", "dataset_manifest", "preprocessing_revision")
REQUIRED_LICENSE_FIELDS = ("implementation", "model_weights", "training_data", "redistribution")


def _require_object(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value


def _require_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where} must be a non-empty string")
    return value


def _require_positive_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{where} must be a positive integer")
    return value


def _validate_tensor(value: Any, where: str) -> None:
    tensor = _require_object(value, where)
    for key in ("name", "dtype", "layout", "role"):
        _require_string(tensor.get(key), f"{where}.{key}")
    shape = tensor.get("shape")
    if not isinstance(shape, list) or not shape:
        raise ValueError(f"{where}.shape must be a non-empty array")
    for index, dimension in enumerate(shape):
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension == 0:
            raise ValueError(f"{where}.shape[{index}] must be a non-zero integer")


def _validate_runtime_extension(root: dict) -> None:
    runtime = root.get("runtime")
    if runtime is None:
        return

    runtime = _require_object(runtime, "manifest.runtime")

    backend = _require_string(
        runtime.get("backend"),
        "manifest.runtime.backend",
    )
    if backend != "onnxruntime":
        raise ValueError(
            "manifest.runtime.backend must be onnxruntime when runtime is present"
        )

    input_name = _require_string(
        runtime.get("input_name"),
        "manifest.runtime.input_name",
    )
    output_name = _require_string(
        runtime.get("output_name"),
        "manifest.runtime.output_name",
    )
    if not input_name or not output_name:
        raise ValueError("manifest.runtime input/output names are required")

    input_names = {
        tensor["name"] for tensor in root["inputs"]
    }
    output_names = {
        tensor["name"] for tensor in root["outputs"]
    }
    if input_name not in input_names:
        raise ValueError(
            "manifest.runtime.input_name must reference an inputs[] tensor"
        )
    if output_name not in output_names:
        raise ValueError(
            "manifest.runtime.output_name must reference an outputs[] tensor"
        )

    if runtime.get("input_dtype") != "int64":
        raise ValueError("manifest.runtime.input_dtype must be int64")

    if runtime.get("token_mode") != "mozart_ids":
        raise ValueError(
            "manifest.runtime.token_mode must be mozart_ids"
        )

    if runtime.get("external_vocabulary_size") != 512:
        raise ValueError(
            "manifest.runtime.external_vocabulary_size must be 512"
        )

    _require_positive_int(
        runtime.get("context_length_tokens"),
        "manifest.runtime.context_length_tokens",
    )
    _require_positive_int(
        runtime.get("max_generated_tokens"),
        "manifest.runtime.max_generated_tokens",
    )

    if runtime["context_length_tokens"] < 2:
        raise ValueError(
            "manifest.runtime.context_length_tokens must be at least 2"
        )
    if runtime["max_generated_tokens"] < 2:
        raise ValueError(
            "manifest.runtime.max_generated_tokens must be at least 2"
        )
    if runtime["context_length_tokens"] > root["context_length_tokens"]:
        raise ValueError(
            "manifest.runtime.context_length_tokens exceeds root context_length_tokens"
        )
    if runtime["max_generated_tokens"] > root["max_generated_tokens"]:
        raise ValueError(
            "manifest.runtime.max_generated_tokens exceeds root max_generated_tokens"
        )

    if runtime.get("bos_token_id") != 1:
        raise ValueError("manifest.runtime.bos_token_id must be 1")
    if runtime.get("eos_token_id") != 2:
        raise ValueError("manifest.runtime.eos_token_id must be 2")

    allow_unhashed = runtime.get("allow_unhashed_experimental", False)
    if not isinstance(allow_unhashed, bool):
        raise ValueError(
            "manifest.runtime.allow_unhashed_experimental must be boolean"
        )


def _reject_placeholders(value: Any, where: str = "manifest") -> None:
    if isinstance(value, str):
        if "<FROZEN>" in value or value == "REPLACE":
            raise ValueError(f"{where} contains an unresolved placeholder")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_placeholders(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_placeholders(item, f"{where}[{index}]")


def validate(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read model manifest {path}: {exc}") from exc

    root = _require_object(data, "manifest")
    for key in REQUIRED_ROOT_FIELDS:
        if key not in root:
            raise ValueError(f"manifest.{key} is required")

    manifest_status = _require_string(root.get("manifest_status"), "manifest.manifest_status")
    if manifest_status not in ALLOWED_STATUS:
        raise ValueError(f"manifest.manifest_status must be one of {sorted(ALLOWED_STATUS)}")
    if root["manifest_schema_version"] != 1:
        raise ValueError("manifest.manifest_schema_version must be 1")

    for key in ("model_id", "model_revision", "model_file", "model_format"):
        _require_string(root[key], f"manifest.{key}")

    model_file = Path(root["model_file"])
    if model_file.is_absolute() or ".." in model_file.parts:
        raise ValueError("manifest.model_file must be a safe relative path")

    model_sha = _require_string(root["model_sha256"], "manifest.model_sha256")
    if model_sha != "<FROZEN>" and not SHA256_RE.fullmatch(model_sha):
        raise ValueError("manifest.model_sha256 must be SHA-256 or <FROZEN>")

    distribution = _require_string(root["distribution_class"], "manifest.distribution_class")
    if distribution not in ALLOWED_DISTRIBUTION:
        raise ValueError(f"manifest.distribution_class must be one of {sorted(ALLOWED_DISTRIBUTION)}")

    if root["vocabulary_id"] != "mozart-midi-events-v1":
        raise ValueError("manifest.vocabulary_id must be mozart-midi-events-v1")
    if root["vocabulary_size"] != 512:
        raise ValueError("manifest.vocabulary_size must be 512")

    _require_positive_int(root["context_length_tokens"], "manifest.context_length_tokens")
    _require_positive_int(root["max_generated_tokens"], "manifest.max_generated_tokens")

    for field in ("inputs", "outputs"):
        values = root[field]
        if not isinstance(values, list) or not values:
            raise ValueError(f"manifest.{field} must be a non-empty array")
        for index, tensor in enumerate(values):
            _validate_tensor(tensor, f"manifest.{field}[{index}]")

    cache = _require_object(root["kv_cache"], "manifest.kv_cache")
    enabled = cache.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("manifest.kv_cache.enabled must be a boolean")
    tensors = cache.get("tensors", [])
    if not isinstance(tensors, list):
        raise ValueError("manifest.kv_cache.tensors must be an array")
    if enabled and not tensors:
        raise ValueError("manifest.kv_cache.tensors must be non-empty when enabled")
    for index, tensor in enumerate(tensors):
        _validate_tensor(tensor, f"manifest.kv_cache.tensors[{index}]")

    quantization = _require_object(root["quantization"], "manifest.quantization")
    for key in ("scheme", "activations", "weights", "scales", "zero_points"):
        if key not in quantization:
            raise ValueError(f"manifest.quantization.{key} is required")

    conditioning = _require_object(root["conditioning"], "manifest.conditioning")
    for key in REQUIRED_CONDITIONING_FIELDS:
        if key not in conditioning:
            raise ValueError(f"manifest.conditioning.{key} is required")

    decoding = _require_object(root["decoding"], "manifest.decoding")
    for key in REQUIRED_DECODING_FIELDS:
        if key not in decoding:
            raise ValueError(f"manifest.decoding.{key} is required")

    provenance = _require_object(root["provenance"], "manifest.provenance")
    for key in REQUIRED_PROVENANCE_FIELDS:
        _require_string(provenance.get(key), f"manifest.provenance.{key}")

    licenses = _require_object(root["licenses"], "manifest.licenses")
    _validate_runtime_extension(root)

    for key in REQUIRED_LICENSE_FIELDS:
        _require_string(licenses.get(key), f"manifest.licenses.{key}")

    if manifest_status == "frozen":
        _reject_placeholders(root)
        if not SHA256_RE.fullmatch(model_sha):
            raise ValueError("frozen manifest.model_sha256 must be a concrete SHA-256 digest")

    return {
        "manifest_schema_version": 1,
        "manifest_status": manifest_status,
        "model_id": root["model_id"],
        "distribution_class": distribution,
        "vocabulary_id": root["vocabulary_id"],
        "vocabulary_size": root["vocabulary_size"],
        "input_count": len(root["inputs"]),
        "output_count": len(root["outputs"]),
        "kv_cache_enabled": enabled,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.manifest)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        "PASS: model manifest "
        f"{result['model_id']} status={result['manifest_status']} "
        f"inputs={result['input_count']} outputs={result['output_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
