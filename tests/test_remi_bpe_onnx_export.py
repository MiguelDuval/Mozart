#!/usr/bin/env python3
"""Unit and graph-contract tests for the separate MidiTok REMI/BPE exporter."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from export_remi_bpe_onnx import (  # noqa: E402
    build_manifest,
    export_loaded_model,
    inspect_miditok_tokenizer,
)
from validate_model_manifest import validate  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "remi_tokenizer_fixture.json"


class TinyCausalLikeModel:
    """Created lazily after torch is imported by the test case."""


class RemiBpeOnnxExportTests(unittest.TestCase):
    def test_fixture_tokenizer_contract_uses_real_vocabulary_ids(self) -> None:
        contract = inspect_miditok_tokenizer(FIXTURE)
        self.assertEqual(contract["tokenization"], "REMI")
        self.assertEqual(contract["vocab_size"], 23)
        self.assertEqual(
            contract["special_token_ids"],
            {
                "PAD_None": 0,
                "BOS_None": 1,
                "EOS_None": 2,
                "MASK_None": 3,
            },
        )
        self.assertEqual(len(contract["tokenizer_sha256"]), 64)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tokenizer.json"
            path.write_text(
                '{"tokenization":"REMI","tokenization":"MMM"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                inspect_miditok_tokenizer(path)

    def test_missing_learned_bpe_model_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base-vocabulary-only-tokenizer.json"
            payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
            payload.pop("_model", None)
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, "missing the serialized _model"
            ):
                inspect_miditok_tokenizer(path)

    def test_non_remi_tokenizer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tokenizer.json"
            payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
            payload["tokenization"] = "MMM"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tokenization='REMI'"):
                inspect_miditok_tokenizer(path)

    def test_exported_graph_supports_dynamic_sequence_and_matches_eager(self) -> None:
        import torch

        class TinyModel(torch.nn.Module):
            def __init__(self, vocabulary_size: int) -> None:
                super().__init__()
                self.config = types.SimpleNamespace(vocab_size=vocabulary_size)
                self.embedding = torch.nn.Embedding(vocabulary_size, 8)
                self.projection = torch.nn.Linear(8, vocabulary_size)

            def forward(self, input_ids):
                return self.projection(self.embedding(input_ids))

        tokenizer_contract = inspect_miditok_tokenizer(FIXTURE)
        model = TinyModel(tokenizer_contract["vocab_size"]).eval()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tiny-remi.onnx"
            report = export_loaded_model(
                model,
                tokenizer_contract,
                output,
                context_length=16,
                sample_sequence_length=4,
                max_generated_tokens=8,
                opset=17,
            )
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)
            self.assertEqual(report["input_shape"], [1, -1])
            self.assertEqual(report["output_shape"], [1, 23])
            self.assertEqual(report["tested_sequence_lengths"], [1, 2, 4])

    def test_remi_manifest_passes_dedicated_runtime_contract(self) -> None:
        tokenizer_contract = inspect_miditok_tokenizer(FIXTURE)
        manifest = build_manifest(
            model_id="remi-fixture",
            model_revision="fixture-rev",
            model_file="model.onnx",
            model_sha256="a" * 64,
            tokenizer_file="tokenizer.json",
            tokenizer_contract=tokenizer_contract,
            context_length=1024,
            max_generated_tokens=400,
            source_code_files_sha256={"gpt_model.py": "b" * 64},
            source_checkpoint_files_sha256={"model.safetensors": "c" * 64},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            validated = validate(path)
        self.assertEqual(validated["vocabulary_id"], "miditok-remi-bpe-v1")
        self.assertEqual(validated["vocabulary_size"], 23)

    def test_remi_manifest_rejects_wrong_tokenizer_vocabulary_size(self) -> None:
        tokenizer_contract = inspect_miditok_tokenizer(FIXTURE)
        manifest = build_manifest(
            model_id="remi-fixture",
            model_revision="fixture-rev",
            model_file="model.onnx",
            model_sha256="a" * 64,
            tokenizer_file="tokenizer.json",
            tokenizer_contract=tokenizer_contract,
            context_length=1024,
            max_generated_tokens=400,
            source_code_files_sha256={"gpt_model.py": "b" * 64},
            source_checkpoint_files_sha256={"model.safetensors": "c" * 64},
        )
        manifest["runtime"]["external_vocabulary_size"] += 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "external_vocabulary_size"):
                validate(path)


if __name__ == "__main__":
    unittest.main()
