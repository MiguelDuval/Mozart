#!/usr/bin/env python3
"""
Regression tests for deterministic per-prompt seeding (Stage 1).

Python's built-in hash() is salted per process (PYTHONHASHSEED) and must never
drive experiment seeds. All Mozart evaluation scripts (evaluate_models.py,
eval_ckpt_metrics.py, gen_checkpoint.py) derive per-prompt seeds from
sha256(prompt_id) via evaluate_models.prompt_seed.

Note: historical JSON reports (e.g. eval-antiforget-step25/metrics_step25.json,
eval-matched-20261027/evaluation_report.json) were generated BEFORE the
hash()-to-sha256 fix, so their recorded seeds are process-salted and cannot be
reproduced. The expected values below are computed with the current
sha256(prompt_id) scheme and define what every (re)run must produce.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from evaluate_models import prompt_seed  # noqa: E402

# Expected seeds for base seed 20261027 under the sha256(prompt_id) scheme.
EXPECTED_SEEDS = {
    ("nrgcp-00", 20261027): 956031960,
    ("nrgcp-05", 20261027): 1188314263,
    ("gmd-06", 20261027): 333314860,
    ("gmd-11", 20261027): 1386116186,
}


class TestPromptSeedDeterminism(unittest.TestCase):
    def test_same_inputs_give_same_seed(self):
        for (prompt_id, base_seed), expected in EXPECTED_SEEDS.items():
            self.assertEqual(prompt_seed(base_seed, prompt_id), expected)
            self.assertEqual(prompt_seed(base_seed, prompt_id), expected)

    def test_different_prompts_give_different_seeds(self):
        seeds = {prompt_seed(20261027, pid) for pid in
                 ("gmd-06", "gmd-07", "gmd-08", "nrgcp-00", "nrgcp-05")}
        self.assertEqual(len(seeds), 5)

    def test_seed_stays_in_int31_range(self):
        for prompt_id in ("gmd-06", "nrgcp-00"):
            seed = prompt_seed(20261027, prompt_id)
            self.assertGreaterEqual(seed, 20261027)
            self.assertLess(seed, 20261027 + 2 ** 31)

    def test_all_entry_points_share_one_seed_scheme(self):
        """gen_checkpoint.py and eval_ckpt_metrics.py must reuse evaluate_models.prompt_seed,
        not recompute seeds inline (and never use Python hash())."""
        import eval_ckpt_metrics  # noqa: E402
        import gen_checkpoint  # noqa: E402

        self.assertIs(eval_ckpt_metrics.prompt_seed, prompt_seed)
        self.assertIs(gen_checkpoint.prompt_seed, prompt_seed)
        for (prompt_id, base_seed), expected in EXPECTED_SEEDS.items():
            self.assertEqual(eval_ckpt_metrics.prompt_seed(base_seed, prompt_id), expected)
            self.assertEqual(gen_checkpoint.prompt_seed(base_seed, prompt_id), expected)


if __name__ == "__main__":
    unittest.main()
