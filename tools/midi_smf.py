#!/usr/bin/env python3
"""Strict Standard MIDI File (SMF) structural validation for the Mozart dataset pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class MidiValidationError(ValueError):
    """Raised when an SMF file is structurally invalid."""


@dataclass(frozen=True)
class MidiFileInfo:
    format_type: int
    track_count: int
    division: int
    bytes_size: int


_CHANNEL_DATA_BYTES = {
    0x8: 2,  # note off
    0x9: 2,  # note on
    0xA: 2,  # poly pressure
    0xB: 2,  # control change
    0xC: 1,  # program change
    0xD: 1,  # channel pressure
    0xE: 2,  # pitch bend
}


def _u16be(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise MidiValidationError("truncated uint16")
    return (data[offset] << 8) | data[offset + 1]


def _u32be(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise MidiValidationError("truncated uint32")
    return (
        (data[offset] << 24)
        | (data[offset + 1] << 16)
        | (data[offset + 2] << 8)
        | data[offset + 3]
    )


def _read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for count in range(4):
        if offset >= len(data):
            raise MidiValidationError("truncated variable-length quantity")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            return value, offset
    raise MidiValidationError("variable-length quantity exceeds four bytes")


def _consume_track_event(data: bytes, offset: int, running_status: int | None) -> tuple[int, int | None, bool]:
    _, offset = _read_vlq(data, offset)
    if offset >= len(data):
        raise MidiValidationError("truncated track event")

    status = data[offset]
    if status < 0x80:
        if running_status is None:
            raise MidiValidationError("data byte encountered without running status")
        status = running_status
    else:
        offset += 1

    if 0x80 <= status <= 0xEF:
        message_type = status >> 4
        data_bytes = _CHANNEL_DATA_BYTES.get(message_type)
        if data_bytes is None:
            raise MidiValidationError(f"unsupported channel status 0x{status:02X}")

        for _ in range(data_bytes):
            if offset >= len(data):
                raise MidiValidationError("truncated MIDI channel event")
            value = data[offset]
            if value & 0x80:
                raise MidiValidationError("MIDI channel data byte has status bit set")
            offset += 1
        return offset, status, True

    # System/common and meta events clear running status in SMF streams.
    running_status = None

    if status == 0xFF:
        if offset >= len(data):
            raise MidiValidationError("truncated meta event type")
        offset += 1
        length, offset = _read_vlq(data, offset)
        end = offset + length
        if end > len(data):
            raise MidiValidationError("truncated meta event payload")
        return end, running_status, False

    if status in (0xF0, 0xF7):
        length, offset = _read_vlq(data, offset)
        end = offset + length
        if end > len(data):
            raise MidiValidationError("truncated sysex event")
        return end, running_status, False

    if status in (0xF1, 0xF3):
        if offset >= len(data):
            raise MidiValidationError("truncated system common event")
        if data[offset] & 0x80:
            raise MidiValidationError("system common data byte has status bit set")
        return offset + 1, running_status, False

    if status == 0xF2:
        if offset + 2 > len(data):
            raise MidiValidationError("truncated song-position event")
        if data[offset] & 0x80 or data[offset + 1] & 0x80:
            raise MidiValidationError("system common data byte has status bit set")
        return offset + 2, running_status, False

    if status == 0xF6:
        return offset, running_status, False

    if status == 0xF8 or 0xFA <= status <= 0xFF:
        # Realtime messages are legal bytes in a MIDI stream but are not
        # expected inside an SMF event stream. FF is handled as meta above.
        raise MidiValidationError(f"unexpected realtime status 0x{status:02X}")

    raise MidiValidationError(f"unsupported system status 0x{status:02X}")


def _validate_track(track: bytes, track_index: int) -> None:
    offset = 0
    running_status: int | None = None
    saw_end_of_track = False

    while offset < len(track):
        before = offset
        offset, running_status, _ = _consume_track_event(track, offset, running_status)
        if offset <= before:
            raise MidiValidationError(f"track {track_index}: parser made no progress")

        # Detect a real End-of-Track meta event by looking at the event bytes
        # from the original offset. This is deliberately explicit instead of
        # relying on the generic meta-event parser.
        scan = before
        _, scan = _read_vlq(track, scan)
        if scan < len(track) and track[scan] == 0xFF:
            scan += 1
            if scan < len(track):
                meta_type = track[scan]
                scan += 1
                length, scan = _read_vlq(track, scan)
                if meta_type == 0x2F and length == 0:
                    saw_end_of_track = True
                    if offset != len(track):
                        raise MidiValidationError(
                                f"track {track_index}: bytes found after End-of-Track"
                        )

    if not saw_end_of_track:
        raise MidiValidationError(f"track {track_index}: missing End-of-Track meta event")


def validate_smf(data: bytes) -> MidiFileInfo:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes-like")
    data = bytes(data)

    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiValidationError("missing MThd header")

    header_length = _u32be(data, 4)
    if header_length != 6:
        raise MidiValidationError("MThd header length must be exactly 6")

    format_type = _u16be(data, 8)
    track_count = _u16be(data, 10)
    division = _u16be(data, 12)

    if format_type not in (0, 1, 2):
        raise MidiValidationError(f"unsupported MIDI file format {format_type}")
    if track_count == 0:
        raise MidiValidationError("MIDI file must contain at least one track")
    if division & 0x8000:
        raise MidiValidationError("SMPTE time division is not supported by Mozart yet")

    offset = 14
    for track_index in range(track_count):
        if offset + 8 > len(data) or data[offset : offset + 4] != b"MTrk":
            raise MidiValidationError(f"track {track_index}: missing MTrk chunk")
        length = _u32be(data, offset + 4)
        offset += 8
        end = offset + length
        if end > len(data):
            raise MidiValidationError(f"track {track_index}: track chunk exceeds file size")
        _validate_track(data[offset:end], track_index)
        offset = end

    if offset != len(data):
        raise MidiValidationError("trailing bytes after final track")

    return MidiFileInfo(
        format_type=format_type,
        track_count=track_count,
        division=division,
        bytes_size=len(data),
    )


def validate_midi_file(path: Path) -> MidiFileInfo:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MidiValidationError(f"cannot read {path}: {exc}") from exc
    return validate_smf(data)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("midi_file", type=Path)
    args = parser.parse_args()

    info = validate_midi_file(args.midi_file)
    print(
        "PASS: "
        f"{args.midi_file} format={info.format_type} "
        f"tracks={info.track_count} division={info.division} bytes={info.bytes_size}"
    )
