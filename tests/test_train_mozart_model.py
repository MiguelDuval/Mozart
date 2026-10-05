#!/usr/bin/env python3
"""Contract tests for the development trainer's tiny-fit repetition mode."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from torch import nn

from train_mozart_model import (
    TokenRecordDataset,
    apply_fit_diagnostic,
    build_grammar_target_mask,
)


def _record() -> dict:
    return {
        "tokens": [1, 16, 68, 160, 258, 2],
        "conditioning": {
            "style": "electronic",
            "substyle": "techno",
            "mood": "driving",
            "rhythm": "straight",
            "role": "bass",
        },
        "performance_controls": {
            "density": 0.1,
            "energy": 0.9,
            "syncopation": 0.5,
            "swing": 0.5,
            "variation": 0.5,
        },
    }


class TrainDatasetTests(unittest.TestCase):
    def test_repeat_expands_examples_without_mutating_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.jsonl"
            path.write_text(
                json.dumps(_record()) + "\n",
                encoding="utf-8",
            )

            dataset = TokenRecordDataset(path, 16, repeat=4)

        self.assertEqual(len(dataset), 4)
        self.assertEqual(dataset[0], dataset[1])
        self.assertEqual(dataset[0], dataset[3])

    def test_repeat_must_be_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.jsonl"
            path.write_text(
                json.dumps(_record()) + "\n",
                encoding="utf-8",
            )

            for repeat in (0, -1):
                with self.assertRaisesRegex(ValueError, "repeat must be positive"):
                    TokenRecordDataset(path, 16, repeat=repeat)


    def test_grammar_target_mask_accepts_valid_targets(self) -> None:
        import torch

        input_ids = torch.tensor([[1, 16, 68, 160, 258]])
        padding_mask = torch.zeros((1, 5), dtype=torch.bool)
        targets = torch.tensor([[16, 68, 160, 258, 2]])

        mask = build_grammar_target_mask(
            input_ids,
            padding_mask,
            targets,
        )

        self.assertTrue(mask[0, 0, 16])
        self.assertTrue(mask[0, 1, 68])
        self.assertTrue(mask[0, 2, 160])
        self.assertTrue(mask[0, 3, 258])
        self.assertTrue(mask[0, 4, 2])
        self.assertFalse(mask[0, 1, 500])

    def test_grammar_target_mask_rejects_invalid_target(self) -> None:
        import torch

        input_ids = torch.tensor([[1, 16, 68]])
        padding_mask = torch.zeros((1, 3), dtype=torch.bool)
        targets = torch.tensor([[16, 68, 500]])

        with self.assertRaisesRegex(
            ValueError,
            "training target is invalid for Mozart grammar",
        ):
            build_grammar_target_mask(
                input_ids,
                padding_mask,
                targets,
            )

    def test_fit_diagnostic_disables_dropout_without_changing_module_shape(self) -> None:
        model = nn.Sequential(
            nn.Linear(4, 4),
            nn.Dropout(p=0.25),
            nn.Sequential(nn.Dropout(p=0.5)),
        )
        apply_fit_diagnostic(model)
        dropouts = [
            module
            for module in model.modules()
            if isinstance(module, nn.Dropout)
        ]
        self.assertEqual(len(dropouts), 2)
        self.assertEqual([module.p for module in dropouts], [0.0, 0.0])
        self.assertEqual(model[0].weight.shape, (4, 4))


if __name__ == "__main__":
    unittest.main()
