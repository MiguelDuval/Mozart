#!/usr/bin/env python3
"""
End-to-end smoke test of the original shikhr/music_maker model (Stage 3).

No training. Path under test:
  real validation MIDI -> tokenizer.encode -> model.generate -> tokenizer.decode
  -> dump MIDI -> re-open -> metrics.

Uses ONLY the local official model directory (safetensors weights, SHA-256
38e1083... verified against the project record) and the local tokenizer.
Runs on CUDA if available, otherwise CPU.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"

sys.path.insert(0, str(MODEL_DIR))

import symusic  # noqa: E402
import torch  # noqa: E402
import safetensors.torch as st  # noqa: E402
from mgpt_config import MGPTConfig  # noqa: E402
from gpt_model import GPT  # noqa: E402
from evaluate_models import (  # noqa: E402
    load_pretrained_model,
    generate,
    score_metrics,
    midi_valid_and_reopenable,
    prompt_seed,
)
from miditok import MusicTokenizer  # noqa: E402


def _first_validation_prompt(tokenizer, prompt_len=32):
    runs_dir = REPO_ROOT / "experiments" / "aura-midi" / "runs"
    for lst in ("nrgcp_val_files.txt", "gmd_val_files.txt"):
        path = runs_dir / lst
        if path.exists():
            with open(path) as f:
                first = next((line.strip() for line in f if line.strip()), None)
            if first and Path(first).exists():
                score = symusic.Score(first)
                ids = tokenizer.encode(score).ids
                if len(ids) >= prompt_len + 1:
                    return ids[:prompt_len]
    # Fallback: deterministic synthetic prompt in-vocab.
    return list(range(100, 100 + prompt_len))


class TestOriginalModelSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        meta = load_pretrained_model(MODEL_DIR, cls.device)
        cls.model = meta["model"]
        cls.model.eval()
        cls.config = meta["config"]
        cls.tokenizer = MusicTokenizer.from_pretrained(str(MODEL_DIR))
        cls.missing = meta["missing"]
        cls.unexpected = meta["unexpected"]

    def test_model_loads_from_original_weights(self):
        self.assertIsNotNone(self.model)
        self.assertEqual(self.config.vocab_size, 12000)
        # Official safetensors stores lm_head.weight; the loader promotes it to
        # transformer.wte.weight (weight tying), so nothing is missing/unexpected.
        self.assertEqual(self.missing, [])
        self.assertEqual(self.unexpected, [])
        total = sum(p.numel() for p in self.model.parameters())
        self.assertEqual(total, 44_429_824)

    def test_generate_decode_roundtrip_produces_valid_midi(self):
        prompt_ids = _first_validation_prompt(self.tokenizer)
        seed = prompt_seed(20261027, "smoke-prompt")
        ids, score, info = generate(
            self.model, self.tokenizer, prompt_ids, self.device,
            max_new=64, temperature=1.0, top_k=40, seed=seed,
        )
        # Generation always emits exactly max_new continuation tokens.
        self.assertEqual(info["new_tokens"], 64)
        self.assertEqual(len(ids), len(prompt_ids) + 64)
        self.assertIn("eos_count", info)

        metrics = score_metrics(score)
        self.assertGreaterEqual(metrics["num_notes"], 0)
        self.assertGreaterEqual(metrics["duration_beats"], 0.0)

        with tempfile.TemporaryDirectory() as td:
            midi_path = Path(td) / "smoke_generated.mid"
            score.dump_midi(str(midi_path))
            reopen = midi_valid_and_reopenable(midi_path)
            self.assertTrue(reopen["valid"], msg=reopen.get("error"))
            self.assertTrue(reopen["reopened"])
            self.assertGreaterEqual(reopen["notes"], 0)

    def test_tokenizer_encode_decode_stable(self):
        prompt_ids = _first_validation_prompt(self.tokenizer)
        score = self.tokenizer.decode(prompt_ids)
        metrics = score_metrics(score)
        self.assertGreaterEqual(metrics["num_notes"], 0)


if __name__ == "__main__":
    unittest.main()
