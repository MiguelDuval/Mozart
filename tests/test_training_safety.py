#!/usr/bin/env python3
"""
Regression tests for training safety checks (Phase N).

Tests that:
  1. check_loss_finite detects non-finite loss (called BEFORE backward)
  2. check_gradients_and_params_finite detects non-finite gradients
     (called AFTER backward) -- this is the bug fix: the gradient check
     must run AFTER loss.backward(), not before.
  3. check_parameters_finite detects non-finite model parameters

Usage (from repo root, .venv-aura):
    .venv-aura\\Scripts\\python.exe -m unittest tests.test_training_safety
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import torch
import torch.nn as nn

# Import from train_sampling_balanced (shares the same safety functions
# pattern as train_antiforgetting.py)
sys.path.insert(0, str(REPO_ROOT))
from train_sampling_balanced import (  # noqa: E402
    check_loss_finite,
    check_gradients_and_params_finite,
    check_parameters_finite,
)


class FakeModel(nn.Module):
    """A minimal model whose parameters we can corrupt for testing."""
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(4, 4)


def _make_state():
    """Create a fresh state dict for safety-check functions."""
    return {
        "safety": {
            "finite_loss_steps": 0,
            "non_finite_loss_steps": 0,
            "non_finite_grad_steps": 0,
            "non_finite_param_steps": 0,
        },
    }


class TestLossFinitenessCheck(unittest.TestCase):
    """check_loss_finite must detect non-finite loss before backward."""

    def test_finite_loss_passes(self):
        state = _make_state()
        loss = torch.tensor(0.5)
        self.assertTrue(check_loss_finite(loss, 1, None, state))

    def test_non_finite_loss_detected(self):
        state = _make_state()
        loss = torch.tensor(float("nan"))
        self.assertFalse(check_loss_finite(loss, 1, None, state))
        self.assertEqual(state["safety"]["non_finite_loss_steps"], 1)

    def test_inf_loss_detected(self):
        state = _make_state()
        loss = torch.tensor(float("inf"))
        self.assertFalse(check_loss_finite(loss, 1, None, state))
        self.assertEqual(state["safety"]["non_finite_loss_steps"], 1)


class TestGradientFinitenessCheck(unittest.TestCase):
    """
    check_gradients_and_params_finite must detect non-finite gradients AFTER
    loss.backward(). This is the bug fix: the gradient check must run AFTER
    backward, not before.
    """

    def test_finite_gradients_pass(self):
        state = _make_state()
        model = FakeModel()
        # Forward + backward to populate gradients
        x = torch.randn(2, 4)
        y = model.linear(x)
        loss = y.sum()
        loss.backward()
        self.assertTrue(check_gradients_and_params_finite(model, 1, None, state))

    def test_non_finite_gradients_detected(self):
        state = _make_state()
        model = FakeModel()
        # Corrupt a gradient manually
        x = torch.randn(2, 4)
        y = model.linear(x)
        loss = y.sum()
        loss.backward()
        # Inject NaN into a gradient (use .grad.data to modify gradient values)
        model.linear.weight.grad.data[0, 0] = float("nan")
        self.assertFalse(check_gradients_and_params_finite(model, 1, None, state))
        self.assertEqual(state["safety"]["non_finite_grad_steps"], 1)

    def test_inf_gradients_detected(self):
        state = _make_state()
        model = FakeModel()
        x = torch.randn(2, 4)
        y = model.linear(x)
        loss = y.sum()
        loss.backward()
        model.linear.weight.grad.data[0, 0] = float("inf")
        self.assertFalse(check_gradients_and_params_finite(model, 1, None, state))
        self.assertEqual(state["safety"]["non_finite_grad_steps"], 1)

    def test_no_gradients_is_ok(self):
        """No gradients (before backward) should not fail the check."""
        state = _make_state()
        model = FakeModel()
        # No backward() called yet -> all grads are None
        self.assertTrue(check_gradients_and_params_finite(model, 1, None, state))


class TestParameterFinitenessCheck(unittest.TestCase):
    """check_parameters_finite must detect non-finite model parameters."""

    def test_finite_parameters_pass(self):
        state = _make_state()
        model = FakeModel()
        self.assertTrue(check_parameters_finite(model, 1, None, state))

    def test_non_finite_parameters_detected(self):
        state = _make_state()
        model = FakeModel()
        model.linear.weight.data[0, 0] = float("nan")
        self.assertFalse(check_parameters_finite(model, 1, None, state))

    def test_inf_parameters_detected(self):
        state = _make_state()
        model = FakeModel()
        model.linear.bias.data[0] = float("-inf")
        self.assertFalse(check_parameters_finite(model, 1, None, state))


if __name__ == "__main__":
    unittest.main()
