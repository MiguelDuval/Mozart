"""Lightweight tests for correct checkpoint selection and loading.

These tests verify that the original pretrained checkpoint and the selected
fine-tuned checkpoint load into the same GPT architecture with the expected
weight-tying behaviour (no shape mismatches, no unexpected keys, only the
weight-tied output head missing from the safetensors file).
"""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # repo root (Mozart/)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"))

from evaluate_models import (  # noqa: E402
    load_pretrained_model,
    load_finetuned_model,
)
from mgpt_config import MGPTConfig  # noqa: E402

MODEL_DIR = REPO / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
FINETUNED = (
    REPO / "experiments" / "aura-midi" / "runs" / "pilot-20261027_145544"
    / "checkpoints" / "checkpoint_best.pt"
)


class TestCheckpointLoading(unittest.TestCase):
    def setUp(self):
        self.device = __import__("torch").device("cpu")

    def test_pretrained_loads_with_expected_missing_keys(self):
        loaded = load_pretrained_model(MODEL_DIR, self.device)
        self.assertIsNotNone(loaded["model"])
        self.assertEqual(len(loaded["unexpected"]), 0, f"unexpected keys: {loaded['unexpected']}")
        # The safetensors file does not store the tied output head separately;
        # exactly that (or the equivalent tied embedding entry) may be missing.
        self.assertIn(len(loaded["missing"]), (1,), f"missing keys: {loaded['missing']}")
        self.assertTrue(
            any("wte" in k or "lm_head" in k for k in loaded["missing"]),
            f"expected a weight-tied key among missing: {loaded['missing']}",
        )

    def test_finetuned_loads_cleanly(self):
        loaded = load_finetuned_model(FINETUNED, MODEL_DIR, self.device)
        self.assertIsNotNone(loaded["model"])
        self.assertEqual(len(loaded["missing"]), 0, f"missing keys: {loaded['missing']}")
        self.assertEqual(len(loaded["unexpected"]), 0, f"unexpected keys: {loaded['unexpected']}")

    def test_checkpoint_metadata_matches_history(self):
        loaded = load_finetuned_model(FINETUNED, MODEL_DIR, self.device)
        self.assertEqual(loaded["step"], 500)
        self.assertAlmostEqual(loaded["best_val_loss"], 2.4509, places=3)

    def test_architecture_matches_config(self):
        cfg = MGPTConfig(**json.loads((MODEL_DIR / "config.json").read_text()))
        self.assertEqual(cfg.vocab_size, 12000)
        self.assertEqual(cfg.n_layer, 12)
        self.assertEqual(cfg.n_head, 8)
        self.assertEqual(cfg.n_embd, 512)
        self.assertEqual(cfg.block_size, 1024)
        self.assertFalse(cfg.bias)


if __name__ == "__main__":
    unittest.main()
