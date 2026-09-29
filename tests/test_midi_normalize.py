#!/usr/bin/env python3
"""Tests for deterministic Mozart MIDI normalization."""

from __future__ import annotations

import struct
import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from midi_normalize import MidiValidationError, normalize_smf


def vlq(value: int) -> bytes:
    if value < 0:
        raise ValueError("VLQ value must be non-negative")
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    parts.reverse()
    return bytes(parts)


def track(events: bytes) -> bytes:
    return b"MTrk" + struct.pack(">I", len(events)) + events


def smf(tracks: list[bytes], format_type: int = 1, division: int = 480) -> bytes:
    header = b"MThd" + struct.pack(">IHHH", 6, format_type, len(tracks), division)
    return header + b"".join(track(item) for item in tracks)


class MidiNormalizeTests(unittest.TestCase):
    def test_multitrack_notes_controls_tempo_and_meter(self) -> None:
        conductor = (
            bytes.fromhex("00 ff 51 03 07 a1 20")
            + bytes.fromhex("00 ff 58 04 04 02 18 08")
            + bytes.fromhex("00 ff 2f 00")
        )
        notes = (
            bytes.fromhex("00 90 3c 64")
            + vlq(480)
            + bytes.fromhex("80 3c 00")
            + vlq(240)
            + bytes.fromhex("b0 01 7f")
            + bytes.fromhex("00 ff 2f 00")
        )

        normalized = normalize_smf(smf([conductor, notes]))

        self.assertEqual(normalized.source_format, 1)
        self.assertEqual(normalized.source_tracks, 2)
        self.assertEqual(normalized.notes[0].start_beat, 0.0)
        self.assertEqual(normalized.notes[0].duration_beats, 1.0)
        self.assertEqual(normalized.notes[0].note, 60)
        self.assertEqual(normalized.notes[0].velocity, 100)
        self.assertEqual(normalized.controls[0].start_beat, 1.5)
        self.assertEqual(normalized.controls[0].controller, 1)
        self.assertEqual(normalized.controls[0].value, 127)
        self.assertAlmostEqual(normalized.tempo_events[0].bpm, 120.0)
        self.assertEqual(normalized.time_signatures[0].numerator, 4)
        self.assertEqual(normalized.time_signatures[0].denominator, 4)

    def test_length_bars_uses_time_signature(self) -> None:
        track_data = (
            bytes.fromhex("00 ff 58 04 03 02 18 08")
            + vlq(5760)
            + bytes.fromhex("b0 01 7f")
            + bytes.fromhex("00 ff 2f 00")
        )
        normalized = normalize_smf(smf([track_data], format_type=0))
        self.assertEqual(normalized.length_beats, 12.0)
        self.assertEqual(normalized.length_bars, 4)


    def test_note_on_velocity_zero_is_note_off(self) -> None:
        track_data = (
            bytes.fromhex("00 90 3c 64")
            + vlq(240)
            + bytes.fromhex("90 3c 00")
            + bytes.fromhex("00 ff 2f 00")
        )
        normalized = normalize_smf(smf([track_data], format_type=0))
        self.assertEqual(len(normalized.notes), 1)
        self.assertEqual(normalized.notes[0].duration_beats, 0.5)

    def test_sub_grid_duration_is_quantized_to_one_step(self) -> None:
        track_data = (
            bytes.fromhex("00 90 3c 64")
            + vlq(20)
            + bytes.fromhex("80 3c 00")
            + bytes.fromhex("00 ff 2f 00")
        )
        normalized = normalize_smf(smf([track_data], format_type=0))
        self.assertEqual(
            normalized.notes[0].duration_beats,
            1.0 / 16.0,
        )

    def test_unmatched_note_off_is_diagnostic_only(self) -> None:
        track_data = bytes.fromhex("00 80 3c 00 00 ff 2f 00")
        normalized = normalize_smf(smf([track_data], format_type=0))
        self.assertEqual(len(normalized.notes), 0)
        self.assertEqual(normalized.dropped_unmatched_note_offs, 1)

    def test_unclosed_note_is_reported(self) -> None:
        track_data = (
            bytes.fromhex("00 90 3c 64")
            + vlq(480)
            + bytes.fromhex("ff 2f 00")
        )
        normalized = normalize_smf(smf([track_data], format_type=0))
        self.assertEqual(normalized.dropped_unclosed_notes, 1)
        self.assertEqual(len(normalized.notes), 0)

    def test_format_two_is_rejected(self) -> None:
        track_data = bytes.fromhex("00 ff 2f 00")
        with self.assertRaises(MidiValidationError):
            normalize_smf(smf([track_data], format_type=2))

    def test_normalization_is_deterministic(self) -> None:
        track_data = (
            bytes.fromhex("00 90 40 64")
            + vlq(480)
            + bytes.fromhex("80 40 00 00 ff 2f 00")
        )
        first = normalize_smf(smf([track_data], format_type=0)).to_json()
        second = normalize_smf(smf([track_data], format_type=0)).to_json()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
