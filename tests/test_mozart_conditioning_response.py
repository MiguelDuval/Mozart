#!/usr/bin/env python3
"""TDD contract for development-model conditioning responsiveness."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


class MozartConditioningResponseTests(unittest.TestCase):
    def test_evaluator_reports_nonzero_response_for_every_control(self) -> None:
        import torch

        sys.path.insert(0, str(TOOLS))
        from mozart_model import ModelConfig, MozartTransformer

        config = ModelConfig(
            model_id="test-conditioning-response",
            vocabulary_id="mozart-midi-events-v1",
            vocabulary_size=512,
            max_sequence_length=16,
            d_model=32,
            nhead=4,
            num_layers=1,
            dim_feedforward=64,
            dropout=0.0,
            tie_token_embeddings=True,
            conditioning_sizes={
                "style": 6,
                "substyle": 7,
                "mood": 8,
                "rhythm": 7,
                "role": 8,
            },
            performance_control_names=(
                "density",
                "energy",
                "syncopation",
                "swing",
                "variation",
            ),
        )
        torch.manual_seed(1234)
        model = MozartTransformer(config)
        model.eval()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "checkpoint.pt"
            torch.save(
                {
                    "model_id": config.model_id,
                    "config": config.__dict__,
                    "epoch": 1,
                    "seed": 1234,
                    "train_loss": 0.0,
                    "validation_loss": 0.0,
                    "model_state": model.state_dict(),
                },
                checkpoint,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "evaluate_mozart_conditioning.py"),
                    str(checkpoint),
                    "--config",
                    str(ROOT / "docs" / "model-training-config.json"),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

        report = json.loads(result.stdout)
        self.assertEqual(
            list(report["controls"]),
            ["density", "energy", "syncopation", "swing", "variation"],
        )
        for name in report["controls"]:
            self.assertGreater(report["controls"][name]["max_abs_delta"], 1e-8)


if __name__ == "__main__":
    unittest.main()
