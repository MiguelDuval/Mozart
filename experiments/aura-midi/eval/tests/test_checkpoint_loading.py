"""Lightweight tests for correct checkpoint selection and loading.

These tests verify that the original pretrained checkpoint and the selected
fine-tuned checkpoint load into the same GPT architecture with the expected
weight-tying behaviour (no shape mismatches, no unexpected keys, no missing
keys: the loader promotes the tied lm_head into the wte state-dict entry).
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

    def test_pretrained_loads_cleanly_with_weight_tying(self):
        loaded = load_pretrained_model(MODEL_DIR, self.device)
        self.assertIsNotNone(loaded["model"])
        # The safetensors stores lm_head.weight but not the tied transformer.wte.weight;
        # the loader promotes lm_head into the wte entry so nothing is missing/unexpected.
        self.assertEqual(loaded["missing"], [], f"missing keys: {loaded['missing']}")
        self.assertEqual(loaded["unexpected"], [], f"unexpected keys: {loaded['unexpected']}")

        # The tied embedding holds the checkpoint's trained lm_head values.
        import torch  # noqa: E402
        import safetensors.torch as st  # noqa: E402
        ckpt = st.load_file(str(MODEL_DIR / "model.safetensors"))
        m = loaded["model"]
        self.assertIs(m.transformer.wte.weight, m.lm_head.weight)
        self.assertTrue(torch.allclose(m.transformer.wte.weight, ckpt["model.lm_head.weight"]))
        self.assertTrue(torch.allclose(m.lm_head.weight, ckpt["model.lm_head.weight"]))

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
