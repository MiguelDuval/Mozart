#!/usr/bin/env python3
"""Tests for Android-compatible real REMI/BPE ONNX token generation."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_remi_bpe_onnx_smoke import run_smoke, select_next_token  # noqa: E402


class FakeTensorInfo:
    def __init__(self, name: str, tensor_type: str):
        self.name = name
        self.type = tensor_type


class FakeSession:
    def __init__(self, logits: np.ndarray):
        self.logits = logits
        self.inputs = [FakeTensorInfo("input_ids", "tensor(int64)")]
        self.outputs = [FakeTensorInfo("logits", "tensor(float)")]
        self.calls = 0

    def get_inputs(self):
        return self.inputs

    def get_outputs(self):
        return self.outputs

    def run(self, output_names, feed):
        self.calls += 1
        self.last_input = feed["input_ids"]
        return [self.logits]


class RemiBpeOnnxSmokeTests(unittest.TestCase):
    def test_argmax_masks_pad_bos_mask_but_keeps_eos_available(self):
        logits = np.asarray([100.0, 90.0, 80.0, 95.0, 70.0], dtype=np.float32)
        self.assertEqual(select_next_token(logits, 5, 0, 1, 2, 3), 2)

    def test_argmax_ignores_individually_non_finite_logits_like_android(self):
        logits = np.asarray([np.nan, 90.0, 80.0, np.inf, 70.0], dtype=np.float32)
        self.assertEqual(select_next_token(logits, 5, 0, 1, 2, 3), 2)

    def test_argmax_fails_when_every_allowed_logit_is_non_finite(self):
        logits = np.asarray([100.0, 90.0, np.nan, 95.0, -np.inf], dtype=np.float32)
        with self.assertRaisesRegex(ValueError, "no usable next token"):
            select_next_token(logits, 5, 0, 1, 2, 3)

    def test_argmax_rejects_duplicate_or_out_of_range_special_ids(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            select_next_token(np.ones(5), 5, 0, 1, 1)
        with self.assertRaisesRegex(ValueError, "outside the vocabulary"):
            select_next_token(np.ones(5), 5, 0, 1, 5)

    def test_run_smoke_uses_android_token_mask_and_stops_at_eos(self):
        manifest = {
            "vocabulary_size": 5,
            "context_length_tokens": 16,
            "runtime": {
                "pad_token_id": 0,
                "bos_token_id": 1,
                "eos_token_id": 2,
                "mask_token_id": 3,
            },
        }
        # EOS is the highest-scoring token remaining after masking PAD/BOS/MASK.
        session = FakeSession(np.asarray([[100.0, 90.0, 80.0, 95.0, 70.0]], dtype=np.float32))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manifest_path = base / "manifest.json"
            output_path = base / "ids.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch("run_remi_bpe_onnx_smoke.ort.InferenceSession", return_value=session):
                report = run_smoke(base / "model.onnx", manifest_path, output_path, 8)
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), [1, 2])
            self.assertEqual(report["generated_token_count_including_bos"], 2)
            self.assertTrue(report["stopped_at_eos"])
            self.assertEqual(session.calls, 1)
            np.testing.assert_array_equal(session.last_input, np.asarray([[1]], dtype=np.int64))


if __name__ == "__main__":
    unittest.main()
