#!/usr/bin/env python3
"""Regression test for Android JNI KeyContext snapshot access."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AndroidJniKeyContextContractTests(unittest.TestCase):
    def test_timing_telemetry_snapshot_boundary_exists(self) -> None:
        jni = (
            ROOT
            / "src"
            / "platform"
            / "android"
            / "MozartJni.cpp"
        ).read_text(encoding="utf-8")
        activity = (
            ROOT
            / "android"
            / "app"
            / "src"
            / "main"
            / "java"
            / "com"
            / "miguelduval"
            / "mozart"
            / "MainActivity.java"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "Java_com_miguelduval_mozart_MainActivity_nativeTimingTelemetrySnapshot",
            jni,
        )
        self.assertIn(
            "captureTimingTelemetrySnapshot()",
            jni,
        )
        self.assertIn(
            "last_target_us=",
            jni,
        )
        self.assertIn(
            "last_send_us=",
            jni,
        )
        self.assertIn(
            "private static native String nativeTimingTelemetrySnapshot();",
            activity,
        )
        self.assertIn(
            '"\\nTIMING  •  " + nativeTimingTelemetrySnapshot()',
            activity,
        )

    def test_generation_factory_receives_resolved_key_scale_field(self) -> None:
        source = (
            ROOT
            / "src"
            / "platform"
            / "android"
            / "MozartJni.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '#include "generation/GenerationRequestFactory.h"',
            source,
        )
        self.assertRegex(
            source,
            r"GenerationRequestFactory::fromPerformanceContext\(\s*"
            r"context\.resolvedKeyScale\s*,",
            re.MULTILINE,
        )
        self.assertNotRegex(
            source,
            r"context\.resolvedKeyScale\s*\(\s*\)",
        )


if __name__ == "__main__":
    unittest.main()
