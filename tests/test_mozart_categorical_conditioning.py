#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class CategoricalConditioningEvaluatorTests(unittest.TestCase):
    def test_torch_logits_accepts_flat_conditioning_fields(self) -> None:
        from evaluate_mozart_categorical_conditioning import _torch_logits
        from mozart_model import ModelConfig, MozartTransformer

        config = ModelConfig(
            model_id="test-categorical-evaluator",
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
        torch.manual_seed(123)
        model = MozartTransformer(config)
        model.eval()

        logits = _torch_logits(
            model,
            [1, 16, 68],
            {
                "style": "dark_techno",
                "substyle": "dark_techno",
                "mood": "hypnotic",
                "rhythm": "syncopated",
                "role": "lead",
            },
            {
                "density": 0.5,
                "energy": 0.5,
                "syncopation": 0.5,
                "swing": 0.5,
                "variation": 0.5,
            },
        )

        self.assertEqual(logits.shape, (512,))
        self.assertTrue(torch.isfinite(torch.from_numpy(logits)).all())


if __name__ == "__main__":
    unittest.main()
