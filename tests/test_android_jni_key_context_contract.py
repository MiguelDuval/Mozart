#!/usr/bin/env python3
"""Regression test for Android JNI KeyContext snapshot access."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AndroidJniKeyContextContractTests(unittest.TestCase):
    def test_generation_request_reads_resolved_key_scale_field(self) -> None:
        source = (
            ROOT
            / "src"
            / "platform"
            / "android"
            / "MozartJni.cpp"
        ).read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"request\.keyScale\s*=\s*context\.resolvedKeyScale\s*;",
        )
        self.assertNotRegex(
            source,
            r"request\.keyScale\s*=\s*context\.resolvedKeyScale\s*\(\s*\)",
        )


if __name__ == "__main__":
    unittest.main()
