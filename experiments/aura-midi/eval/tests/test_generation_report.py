"""Lightweight tests for valid token IDs, reproducible prompt/seed config,
MIDI save/reopen validation, and accurate provenance recording."""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import symusic  # noqa: E402

RUN_DIR = REPO / "experiments" / "aura-midi" / "eval" / "runs" / "eval-matched-20261027"
REPORT_PATH = RUN_DIR / "evaluation_report.json"


class TestGenerationReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text())
        cls.tokenizer = cls.report["tokenizer"]
        cls.generations = cls.report["generations"]

    def test_tokenizer_provenance_recorded(self):
        self.assertEqual(self.tokenizer["vocab_size"], 12000)
        self.assertTrue(self.tokenizer["revision_sha256"])
        self.assertIn("shikhr-music-maker-official", self.tokenizer["dir"])

    def test_model_and_checkpoint_provenance(self):
        for name in ("pretrained", "finetuned"):
            m = self.report["models"][name]
            self.assertTrue(m["ckpt_sha256"], f"{name} ckpt sha256 missing")
            self.assertEqual(m["config"]["vocab_size"], 12000)
        self.assertEqual(self.report["models"]["pretrained"]["ckpt_sha256"],
                         "38e1083aea069e298f40373ebc394211b66b876702df91b2c4488cbd53079319")
        self.assertEqual(self.report["models"]["finetuned"]["step"], 500)

    def test_decoding_configuration_recorded(self):
        dec = self.report["decoding"]
        self.assertEqual(dec["max_new"], 100)
        self.assertEqual(dec["temperature"], 1.0)
        self.assertEqual(dec["top_k"], 40)
        self.assertEqual(dec["seed"], 20261027)

    def test_prompt_and_seed_provenance_per_generation(self):
        by_prompt = {}
        for g in self.generations:
            self.assertIn(g["model"], ("pretrained", "finetuned"))
            self.assertTrue(g["prompt_id"])
            self.assertTrue(g["source"] in ("nrgcp", "gmd"))
            self.assertEqual(len(g["prompt_ids"]), g["prompt_len"])
            self.assertIsInstance(g["seed"], int)
            self.assertEqual(g["decode"]["max_new"], 100)
            self.assertEqual(g["decode"]["temperature"], 1.0)
            self.assertEqual(g["decode"]["top_k"], 40)
            by_prompt.setdefault(g["prompt_id"], []).append(g)
        # Matched conditions: the same prompt_id uses the SAME seed in both models.
        for pid, gs in by_prompt.items():
            self.assertEqual(len(gs), 2, f"both models must generate {pid}")
            seeds = {g["seed"] for g in gs}
            self.assertEqual(len(seeds), 1, f"seed not matched across models for {pid}")
        # Deterministic: seed derived from prompt_id is stable across models.
        seeds = {g["seed"] for g in self.generations}
        self.assertEqual(len(seeds), len(by_prompt), "seeds not deterministic per prompt")

    def test_all_token_ids_valid(self):
        vocab = self.tokenizer["vocab_size"]
        for g in self.generations:
            for tid in g["prompt_ids"]:
                self.assertGreaterEqual(tid, 0)
                self.assertLess(tid, vocab, f"invalid prompt token {tid} in {g['prompt_id']}")

    def test_midi_save_and_reopen_validation(self):
        for g in self.generations:
            path = Path(g["midi_path"])
            self.assertTrue(path.exists(), f"missing midi {path}")
            # Reopening must succeed (MIDI validity) even for empty outputs,
            # which are a legitimate finding (premature termination).
            score = symusic.Score(str(path))
            self.assertGreater(score.tpq, 0)
            self.assertTrue(g["reopen"]["valid"], f"not valid: {g['reopen']}")
            self.assertTrue(g["reopen"]["reopened"], f"not reopenable: {g['reopen']}")

    def test_both_models_generated_all_prompts(self):
        pre = [g for g in self.generations if g["model"] == "pretrained"]
        ft = [g for g in self.generations if g["model"] == "finetuned"]
        pre_ids = {g["prompt_id"] for g in pre}
        ft_ids = {g["prompt_id"] for g in ft}
        self.assertEqual(pre_ids, ft_ids, "prompt sets must be matched across models")
        self.assertGreaterEqual(len(pre_ids), 12, "need at least 12 representative prompts")


if __name__ == "__main__":
    unittest.main()
