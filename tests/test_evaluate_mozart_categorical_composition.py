#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class CategoricalCompositionEvaluatorTests(unittest.TestCase):
    def test_additivity_reports_zero_residual_for_additive_logits(self) -> None:
        from evaluate_mozart_categorical_composition import _additivity

        base = np.array([0.0, 1.0, -1.0, 2.0], dtype=np.float32)
        single_a = base + np.array([1.0, 0.0, 2.0, -1.0], dtype=np.float32)
        single_b = base + np.array([-2.0, 1.0, 0.0, 3.0], dtype=np.float32)
        combo = base + (single_a - base) + (single_b - base)

        result = _additivity(base, [single_a, single_b], combo)

        self.assertAlmostEqual(result["interaction_residual_ratio"], 0.0, places=6)
        self.assertAlmostEqual(result["actual_vs_additive_cosine"], 1.0, places=6)

    def test_additivity_handles_zero_effect(self) -> None:
        from evaluate_mozart_categorical_composition import _additivity

        base = np.zeros(8, dtype=np.float32)
        result = _additivity(base, [base.copy()], base.copy())

        self.assertEqual(result["centered_actual_delta_l2"], 0.0)
        self.assertEqual(result["interaction_residual_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
