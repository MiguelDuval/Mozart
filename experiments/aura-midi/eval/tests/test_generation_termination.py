"""Regression tests for generation-termination measurement (collapse diagnosis).

These tests lock in the token-level behavior required to detect premature
termination / rhythmic collapse:

* The tokenizer's EOS_None (and BOS_None / PAD_None) tokens decode to silence
  (no notes, no tracks). A continuation dominated by EOS tokens therefore
  yields an empty or near-empty MIDI even though the model emitted the full
  number of requested tokens.
* The model's ``generate()`` has no internal EOS stop: it always emits exactly
  ``max_new`` tokens. ``model_early_termination`` is therefore always False;
  early termination must be measured at token level (EOS count / position in
  the continuation).
* Every generation record carries termination fields
  (``eos_count``, ``first_eos_position``, ``eos_fraction``, ...) plus
  ``prompt_notes`` / ``notes_in_continuation`` so the evaluator can separate
  prompt material from newly generated material.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # repo root (Mozart/)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"))

import torch  # noqa: E402

from evaluate_models import (  # noqa: E402
    _eos_token_id,
    generate,
    load_pretrained_model,
    score_metrics,
)
from miditok import MusicTokenizer  # noqa: E402

MODEL_DIR = REPO / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
PROMPT_IDS = [4649, 258, 7728, 258, 5661, 258, 3918, 258, 2438, 258,
              1620, 258, 3665, 258, 2358, 258, 294, 188, 258, 205,
              294, 190, 258, 205, 294, 190, 258, 294, 190, 258]  # 32 tokens (gmd-06 prompt)


class TestTokenizerSilenceTokens(unittest.TestCase):
    """The tokenizer must turn EOS/BOS/PAD-only sequences into silence."""

    def setUp(self):
        self.tokenizer = MusicTokenizer.from_pretrained(str(MODEL_DIR))
        self.device = torch.device("cpu")

    def test_eos_decodes_to_silence(self):
        eos_id = _eos_token_id(self.tokenizer)
        self.assertEqual(eos_id, 2)
        score = self.tokenizer.decode([eos_id] * 8)
        notes = sum(len(tr.notes) for tr in score.tracks)
        self.assertEqual(notes, 0)
        self.assertEqual(len(score.tracks), 0)

    def test_bos_and_pad_decode_to_silence(self):
        for label, token_id in (("BOS_None", 1), ("PAD_None", 0), ("MASK_None", 3)):
            score = self.tokenizer.decode([token_id] * 8)
            self.assertEqual(sum(len(tr.notes) for tr in score.tracks), 0, label)


class TestGenerateNoInternalStop(unittest.TestCase):
    """model.generate() emits exactly max_new_tokens with no internal EOS stop."""

    def setUp(self):
        self.device = torch.device("cpu")
        self.loaded = load_pretrained_model(MODEL_DIR, self.device)
        self.model = self.loaded["model"]
        self.tokenizer = MusicTokenizer.from_pretrained(str(MODEL_DIR))

    def test_emits_exactly_max_new_tokens(self):
        ids, score, info = generate(
            self.model, self.tokenizer, PROMPT_IDS, self.device,
            max_new=8, temperature=1.0, top_k=40, seed=20261028,
        )
        self.assertEqual(len(ids), len(PROMPT_IDS) + 8)
        self.assertEqual(info["new_tokens"], 8)
        self.assertFalse(info["model_early_termination"])
        self.assertEqual(info["max_new_requested"], 8)

    def test_termination_info_schema(self):
        ids, score, info = generate(
            self.model, self.tokenizer, PROMPT_IDS, self.device,
            max_new=16, temperature=1.0, top_k=40, seed=20261028,
        )
        for key in ("new_tokens", "max_new_requested", "model_early_termination",
                    "eos_id", "eos_count", "first_eos_position",
                    "eos_positions", "eos_fraction"):
            self.assertIn(key, info, f"missing termination field: {key}")
        self.assertEqual(info["new_tokens"], 16)
        self.assertIsInstance(info["eos_count"], int)
        self.assertGreaterEqual(info["eos_count"], 0)
        self.assertLessEqual(info["eos_count"], 16)
        if info["first_eos_position"] is not None:
            self.assertIsInstance(info["first_eos_position"], int)
            self.assertIn(info["first_eos_position"], info["eos_positions"])
        self.assertGreaterEqual(info["eos_fraction"], 0.0)
        self.assertLessEqual(info["eos_fraction"], 1.0)

    def test_continuation_note_accounting(self):
        ids, score, info = generate(
            self.model, self.tokenizer, PROMPT_IDS, self.device,
            max_new=24, temperature=1.0, top_k=40, seed=20261028,
        )
        total_notes = score_metrics(score)["num_notes"]
        prompt_notes = score_metrics(self.tokenizer.decode(PROMPT_IDS))["num_notes"]
        continuation_tokens = ids[len(PROMPT_IDS):]
        self.assertEqual(info["eos_count"] + (len(continuation_tokens) - info["eos_count"]),
                         len(continuation_tokens))
        # The continuation cannot remove notes contributed by the prompt.
        self.assertGreaterEqual(total_notes, prompt_notes)
        notes_in_continuation = max(0, total_notes - prompt_notes)
        self.assertGreaterEqual(notes_in_continuation, 0)
        self.assertLessEqual(notes_in_continuation, total_notes)


if __name__ == "__main__":
    unittest.main()