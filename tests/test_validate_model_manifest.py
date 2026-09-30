#!/usr/bin/env python3
"""Tests for the machine-readable Mozart model manifest validator."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from validate_model_manifest import validate


def template_manifest() -> dict:
    return {
        "manifest_schema_version": 1,
        "manifest_status": "template",
        "model_id": "<FROZEN>",
        "model_revision": "<FROZEN>",
        "model_file": "<FROZEN>",
        "model_format": "<FROZEN>",
        "model_sha256": "<FROZEN>",
        "distribution_class": "private_experimental",
        "vocabulary_id": "mozart-midi-events-v1",
        "vocabulary_size": 512,
        "context_length_tokens": 1024,
        "max_generated_tokens": 512,
        "inputs": [{"name": "<FROZEN>", "dtype": "<FROZEN>", "shape": [-1, 1024],
                    "layout": "<FROZEN>", "role": "token_ids"}],
        "outputs": [{"name": "<FROZEN>", "dtype": "<FROZEN>", "shape": [-1, 512],
                     "layout": "<FROZEN>", "role": "token_scores"}],
        "kv_cache": {"enabled": False, "tensors": []},
        "quantization": {
            "scheme": "<FROZEN>", "activations": "<FROZEN>", "weights": "<FROZEN>",
            "scales": "<FROZEN>", "zero_points": "<FROZEN>",
        },
        "conditioning": {
            key: "<FROZEN>" for key in (
                "style_family", "substyle", "mood", "rhythm", "role", "key_scale",
                "chords", "density", "energy", "syncopation", "swing", "variation", "seed",
            )
        },
        "decoding": {
            key: "<FROZEN>" for key in (
                "strategy", "temperature", "top_k", "top_p", "seed_policy",
            )
        },
        "provenance": {
            "training_source": "<FROZEN>",
            "dataset_manifest": "<FROZEN>",
            "preprocessing_revision": "<FROZEN>",
        },
        "licenses": {
            "implementation": "<FROZEN>",
            "model_weights": "<FROZEN>",
            "training_data": "<FROZEN>",
            "redistribution": "<FROZEN>",
        },
    }


class ModelManifestValidationTests(unittest.TestCase):
    def _write(self, manifest: dict, root: Path) -> Path:
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_template_manifest_structure_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = validate(self._write(template_manifest(), Path(directory)))
            self.assertEqual(result["manifest_status"], "template")

    def test_frozen_manifest_rejects_placeholders(self) -> None:
        manifest = template_manifest()
        manifest.update({
            "manifest_status": "frozen",
            "model_id": "mozart-test",
            "model_revision": "rev-1",
            "model_file": "models/test.tflite",
            "model_format": "tflite",
            "model_sha256": "a" * 64,
        })
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate(self._write(manifest, Path(directory)))

    def test_frozen_manifest_with_concrete_values_passes(self) -> None:
        manifest = template_manifest()
        manifest.update({
            "manifest_status": "frozen",
            "model_id": "mozart-test",
            "model_revision": "rev-1",
            "model_file": "models/test.tflite",
            "model_format": "tflite",
            "model_sha256": "a" * 64,
        })
        for group in ("inputs", "outputs"):
            for tensor in manifest[group]:
                tensor["name"] = "tensor"
                tensor["dtype"] = "int8"
                tensor["layout"] = "row_major"
        for section in ("quantization", "conditioning", "decoding", "provenance", "licenses"):
            for key in manifest[section]:
                manifest[section][key] = "concrete"
        with tempfile.TemporaryDirectory() as directory:
            result = validate(self._write(manifest, Path(directory)))
            self.assertEqual(result["manifest_status"], "frozen")

    def test_wrong_vocabulary_is_rejected(self) -> None:
        manifest = template_manifest()
        manifest["vocabulary_size"] = 513
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate(self._write(manifest, Path(directory)))

    def test_unsafe_model_path_is_rejected(self) -> None:
        manifest = template_manifest()
        manifest["model_file"] = "../model.tflite"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate(self._write(manifest, Path(directory)))


    def test_experimental_onnx_runtime_extension_passes(self) -> None:
        manifest = template_manifest()
        manifest["model_format"] = "onnx"
        manifest["runtime"] = {
            "backend": "onnxruntime",
            "input_name": "input_ids",
            "output_name": "logits",
            "input_dtype": "int64",
            "token_mode": "mozart_ids",
            "external_vocabulary_size": 512,
            "context_length_tokens": 1024,
            "max_generated_tokens": 512,
            "bos_token_id": 1,
            "eos_token_id": 2,
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            result = validate(self._write(manifest, Path(directory)))
            self.assertEqual(result["manifest_status"], "template")

    def test_experimental_onnx_runtime_rejects_wrong_bos(self) -> None:
        manifest = template_manifest()
        manifest["model_format"] = "onnx"
        manifest["runtime"] = {
            "backend": "onnxruntime",
            "input_name": "input_ids",
            "output_name": "logits",
            "input_dtype": "int64",
            "token_mode": "mozart_ids",
            "external_vocabulary_size": 512,
            "context_length_tokens": 1024,
            "max_generated_tokens": 512,
            "bos_token_id": 99,
            "eos_token_id": 2,
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate(self._write(manifest, Path(directory)))


    def test_enabled_kv_cache_requires_tensors(self) -> None:
        manifest = copy.deepcopy(template_manifest())
        manifest["kv_cache"]["enabled"] = True
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate(self._write(manifest, Path(directory)))


if __name__ == "__main__":
    unittest.main()
