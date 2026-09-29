#!/usr/bin/env python3
"""End-to-end SMF -> normalized events -> Mozart tokens test."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from midi_to_training_example import build_example


def smf_fixture() -> bytes:
    # 4 bars, PPQ 480: C2 on beats 0, 1, 2, 3 repeated over four bars.
    def vlq(value: int) -> bytes:
        parts = [value & 0x7F]
        value >>= 7
        while value:
            parts.append((value & 0x7F) | 0x80)
            value >>= 7
        parts.reverse()
        return bytes(parts)

    events = bytearray()
    for _ in range(4):
        events += bytes.fromhex("00 90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
        events += vlq(240) + bytes.fromhex("90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
        events += vlq(240) + bytes.fromhex("90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
        events += vlq(240) + bytes.fromhex("90 3C 64")
        events += vlq(240) + bytes.fromhex("80 3C 00")
    events += bytes.fromhex("00 FF 2F 00")

    header = b"MThd" + bytes.fromhex("00 00 00 06 00 00 00 01 01 E0")
    track = b"MTrk" + len(events).to_bytes(4, "big") + bytes(events)
    return header + track


class MidiToTrainingExampleTests(unittest.TestCase):
    def test_end_to_end_example(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.mid"
            path.write_bytes(smf_fixture())

            result = build_example(
                path,
                source_id="fixture-song",
                source_revision="fixture-rev-1",
                source_path="fixtures/four-bars.mid",
                style="electronic",
                substyle="techno",
                mood="driving",
                rhythm="straight",
                role="bass",
                seed=12345,
            )

        self.assertEqual(result["source_id"], "fixture-song")
        self.assertEqual(result["source_revision"], "fixture-rev-1")
        self.assertEqual(result["source_path"], "fixtures/four-bars.mid")
        self.assertEqual(result["vocabulary_id"], "mozart-midi-events-v1")
        self.assertEqual(result["vocabulary_size"], 512)
        self.assertEqual(result["music"]["length_bars"], 4)
        self.assertEqual(result["conditioning"]["substyle"], "techno")
        self.assertEqual(result["conditioning"]["seed"], 12345)
        self.assertEqual(result["tokens"][0], 1)
        self.assertEqual(result["tokens"][-1], 2)
        self.assertGreater(len(result["tokens"]), 2)

    def test_source_identity_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.mid"
            path.write_bytes(smf_fixture())

            with self.assertRaises(ValueError):
                build_example(path, source_id=" ", source_revision="fixture-rev-1")

            with self.assertRaises(ValueError):
                build_example(path, source_id="fixture-song", source_revision=" ")


if __name__ == "__main__":
    unittest.main()
