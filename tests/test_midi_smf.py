#!/usr/bin/env python3
"""Tests for the strict SMF structural validator."""

from __future__ import annotations

import struct
import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from midi_smf import MidiValidationError, validate_smf


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


def make_smf(track: bytes, format_type: int = 0, division: int = 480) -> bytes:
    header = b"MThd" + struct.pack(">IHHH", 6, format_type, 1, division)
    return header + b"MTrk" + struct.pack(">I", len(track)) + track


class MidiSmfTests(unittest.TestCase):
    def test_valid_minimal_midi(self) -> None:
        track = (
            b"\x00\xFF\x51\x03\x07\xA1\x20"
            + b"\x00\x90\x3C\x64"
            + vlq(480) + b"\x80\x3C\x00"
            + b"\x00\xFF\x2F\x00"
        )
        info = validate_smf(make_smf(track))
        self.assertEqual(info.format_type, 0)
        self.assertEqual(info.track_count, 1)
        self.assertEqual(info.division, 480)

    def test_valid_running_status(self) -> None:
        track = (
            b"\x00\x90\x3C\x64"
            + vlq(120) + b"\x40\x50"
            + vlq(120) + b"\x3E\x55"
            + b"\x00\xFF\x2F\x00"
        )
        validate_smf(make_smf(track))

    def test_missing_header(self) -> None:
        with self.assertRaises(MidiValidationError):
            validate_smf(b"not-midi")

    def test_wrong_header_length(self) -> None:
        data = b"MThd" + struct.pack(">IHHH", 5, 0, 1, 480)
        with self.assertRaises(MidiValidationError):
            validate_smf(data)

    def test_smpte_division_is_rejected(self) -> None:
        with self.assertRaises(MidiValidationError):
            validate_smf(make_smf(b"\x00\xFF\x2F\x00", division=0xE250))

    def test_missing_track_end(self) -> None:
        with self.assertRaises(MidiValidationError):
            validate_smf(make_smf(b"\x00\x90\x3C\x64"))

    def test_truncated_channel_event(self) -> None:
        with self.assertRaises(MidiValidationError):
            validate_smf(make_smf(b"\x00\x90\x3C\x64\x00\x80\x3C"))

    def test_invalid_running_status(self) -> None:
        with self.assertRaises(MidiValidationError):
            validate_smf(make_smf(b"\x00\x3C\x64\x00\xFF\x2F\x00"))

    def test_bytes_after_end_of_track_are_rejected(self) -> None:
        track = b"\x00\xFF\x2F\x00\x00\x90\x3C\x64"
        with self.assertRaises(MidiValidationError):
            validate_smf(make_smf(track))

    def test_vlq_overflow_is_rejected(self) -> None:
        bad_delta = b"\x80\x80\x80\x80\x00"
        with self.assertRaises(MidiValidationError):
            validate_smf(make_smf(bad_delta + b"\x00\xFF\x2F\x00"))


if __name__ == "__main__":
    unittest.main()
