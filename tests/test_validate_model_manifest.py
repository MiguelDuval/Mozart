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


def add_experimental_onnx_structure(manifest: dict) -> dict:
    manifest["model_format"] = "onnx"
    manifest["inputs"] = [
        {"name": "input_ids", "dtype": "int64", "shape": [1, -1],
         "layout": "batch_sequence", "role": "token_ids"},
        {"name": "style_id", "dtype": "int64", "shape": [1],
         "layout": "batch", "role": "style_condition"},
        {"name": "substyle_id", "dtype": "int64", "shape": [1],
         "layout": "batch", "role": "substyle_condition"},
        {"name": "mood_id", "dtype": "int64", "shape": [1],
         "layout": "batch", "role": "mood_condition"},
        {"name": "rhythm_id", "dtype": "int64", "shape": [1],
         "layout": "batch", "role": "rhythm_condition"},
        {"name": "role_id", "dtype": "int64", "shape": [1],
         "layout": "batch", "role": "role_condition"},
        {"name": "performance_controls", "dtype": "float32", "shape": [1, 5],
         "layout": "batch_performance_controls", "role": "performance_condition"},
    ]
    manifest["outputs"] = [
        {"name": "logits", "dtype": "float32", "shape": [-1, -1, 512],
         "layout": "batch_sequence_vocabulary", "role": "token_scores"}
    ]
    return manifest



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


    def test_experimental_onnx_conditioning_order_is_canonical(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "experimental-onnx-manifest.example.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            manifest["runtime"]["conditioning_input_names"],
            [
                "style_id",
                "substyle_id",
                "mood_id",
                "rhythm_id",
                "role_id",
                "performance_controls",
            ],
        )
        self.assertEqual(
            manifest["runtime"]["performance_control_names"],
            ["density", "energy", "syncopation", "swing", "variation"],
        )

    def test_experimental_onnx_runtime_extension_passes(self) -> None:
        manifest = template_manifest()
        manifest["model_format"] = "onnx"
        add_experimental_onnx_structure(manifest)
        manifest["inputs"][0]["name"] = "input_ids"
        manifest["inputs"][0]["dtype"] = "int64"
        manifest["outputs"][0]["name"] = "logits"
        manifest["outputs"][0]["dtype"] = "float32"
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
            "conditioning_input_names": [
                "style_id",
                "substyle_id",
                "mood_id",
                "rhythm_id",
                "role_id",
                "performance_controls",
            ],
            "performance_control_names": [
                "density",
                "energy",
                "syncopation",
                "swing",
                "variation",
            ],
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            result = validate(self._write(manifest, Path(directory)))
            self.assertEqual(result["manifest_status"], "template")

    def test_experimental_onnx_runtime_rejects_wrong_bos(self) -> None:
        manifest = template_manifest()
        manifest["model_format"] = "onnx"
        add_experimental_onnx_structure(manifest)
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
            "conditioning_input_names": [
                "style_id",
                "substyle_id",
                "mood_id",
                "rhythm_id",
                "role_id",
                "performance_controls",
            ],
            "performance_control_names": [
                "density",
                "energy",
                "syncopation",
                "swing",
                "variation",
            ],
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate(self._write(manifest, Path(directory)))



    def test_experimental_onnx_runtime_rejects_unknown_input(self) -> None:
        manifest = template_manifest()
        manifest["model_format"] = "onnx"
        manifest["runtime"] = {
            "backend": "onnxruntime",
            "input_name": "missing_input",
            "output_name": "<FROZEN>",
            "input_dtype": "int64",
            "token_mode": "mozart_ids",
            "external_vocabulary_size": 512,
            "context_length_tokens": 1024,
            "max_generated_tokens": 512,
            "bos_token_id": 1,
            "eos_token_id": 2,
            "conditioning_input_names": [
                "style_id",
                "substyle_id",
                "mood_id",
                "rhythm_id",
                "role_id",
                "performance_controls",
            ],
            "performance_control_names": [
                "density",
                "energy",
                "syncopation",
                "swing",
                "variation",
            ],
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate(self._write(manifest, Path(directory)))

    def test_experimental_onnx_runtime_cannot_exceed_root_limits(self) -> None:
        manifest = template_manifest()
        manifest["model_format"] = "onnx"
        add_experimental_onnx_structure(manifest)
        manifest["runtime"] = {
            "backend": "onnxruntime",
            "input_name": "<FROZEN>",
            "output_name": "<FROZEN>",
            "input_dtype": "int64",
            "token_mode": "mozart_ids",
            "external_vocabulary_size": 512,
            "context_length_tokens": 2048,
            "max_generated_tokens": 1024,
            "bos_token_id": 1,
            "eos_token_id": 2,
            "conditioning_input_names": [
                "style_id",
                "substyle_id",
                "mood_id",
                "rhythm_id",
                "role_id",
                "performance_controls",
            ],
            "performance_control_names": [
                "density",
                "energy",
                "syncopation",
                "swing",
                "variation",
            ],
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


    def test_experimental_onnx_runtime_rejects_missing_conditioning_tensor(self) -> None:
        manifest = add_experimental_onnx_structure(template_manifest())
        manifest["inputs"] = [
            tensor for tensor in manifest["inputs"] if tensor["name"] != "style_id"
        ]
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
            "conditioning_input_names": [
                "style_id",
                "substyle_id",
                "mood_id",
                "rhythm_id",
                "role_id",
                "performance_controls",
            ],
            "performance_control_names": [
                "density", "energy", "syncopation", "swing", "variation"
            ],
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "style_id"):
                validate(self._write(manifest, Path(directory)))

    def test_experimental_onnx_runtime_rejects_wrong_conditioning_dtype(self) -> None:
        manifest = add_experimental_onnx_structure(template_manifest())
        manifest["inputs"][1]["dtype"] = "float32"
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
            "conditioning_input_names": [
                "style_id", "substyle_id", "mood_id", "rhythm_id",
                "role_id", "performance_controls"
            ],
            "performance_control_names": [
                "density", "energy", "syncopation", "swing", "variation"
            ],
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "style_id.*int64"):
                validate(self._write(manifest, Path(directory)))

    def test_experimental_onnx_runtime_rejects_wrong_performance_shape(self) -> None:
        manifest = add_experimental_onnx_structure(template_manifest())
        manifest["inputs"][-1]["shape"] = [1, 4]
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
            "conditioning_input_names": [
                "style_id", "substyle_id", "mood_id", "rhythm_id",
                "role_id", "performance_controls"
            ],
            "performance_control_names": [
                "density", "energy", "syncopation", "swing", "variation"
            ],
            "allow_unhashed_experimental": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "performance_controls.*shape"):
                validate(self._write(manifest, Path(directory)))

    def test_input_tensor_names_must_be_unique(self) -> None:
        manifest = template_manifest()
        manifest["inputs"].append(copy.deepcopy(manifest["inputs"][0]))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "inputs.*unique"):
                validate(self._write(manifest, Path(directory)))

    def test_tensor_shape_rejects_invalid_negative_dimension(self) -> None:
        manifest = template_manifest()
        manifest["inputs"][0]["shape"] = [-2, 1024]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "shape\[0\]"):
                validate(self._write(manifest, Path(directory)))



    def test_experimental_onnx_runtime_requires_fixed_token_io_names(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "experimental-onnx-manifest.example.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["runtime"]["input_name"] = "style_id"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                ValueError, "input_name.*input_ids"
            ):
                validate(self._write(manifest, Path(directory)))


if __name__ == "__main__":
    unittest.main()
