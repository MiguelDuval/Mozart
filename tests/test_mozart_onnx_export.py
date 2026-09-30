#!/usr/bin/env python3
"""End-to-end validation of the development Mozart checkpoint -> ONNX ABI."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


class MozartOnnxExportTests(unittest.TestCase):
    def test_export_checkpoint_and_inspect_tensor_abi(self) -> None:
        import torch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "checkpoint.pt"
            output = root / "model.onnx"

            sys.path.insert(0, str(TOOLS))
            from mozart_model import ModelConfig, MozartTransformer

            config = ModelConfig.from_json(
                ROOT / "docs" / "model-training-config.json"
            )
            torch.manual_seed(1234)
            model = MozartTransformer(config)
            model.eval()

            checkpoint_payload = {
                "model_id": config.model_id,
                "config": config.__dict__,
                "epoch": 1,
                "seed": 1234,
                "train_loss": 0.0,
                "validation_loss": 0.0,
                "model_state": model.state_dict(),
                "optimizer_state": {},
            }
            torch.save(checkpoint_payload, checkpoint)

            export = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "export_mozart_onnx.py"),
                    str(checkpoint),
                    str(output),
                    "--config",
                    str(ROOT / "docs" / "model-training-config.json"),
                    "--sequence-length",
                    "8",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("PASS: exported mozart-symbolic-transformer-v0", export.stdout)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)

            inspect = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "inspect_mozart_onnx.py"),
                    str(output),
                    "--config",
                    str(ROOT / "docs" / "model-training-config.json"),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(inspect.stdout)
            self.assertEqual(report["model_id"], "mozart-symbolic-transformer-v0")
            self.assertEqual(report["vocabulary_size"], 512)
            self.assertEqual(
                report["inputs"],
                [
                    {
                        "name": "input_ids",
                        "dtype": "int64",
                        "shape": ["batch", "sequence"],
                    },
                    {"name": "style_id", "dtype": "int64", "shape": ["batch"]},
                    {"name": "substyle_id", "dtype": "int64", "shape": ["batch"]},
                    {"name": "mood_id", "dtype": "int64", "shape": ["batch"]},
                    {"name": "rhythm_id", "dtype": "int64", "shape": ["batch"]},
                    {"name": "role_id", "dtype": "int64", "shape": ["batch"]},
                ],
            )
            self.assertEqual(
                report["outputs"],
                [
                    {
                        "name": "logits",
                        "dtype": "float32",
                        "shape": ["batch", "sequence", 512],
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
