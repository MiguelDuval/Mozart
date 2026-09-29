#!/usr/bin/env python3
"""Deterministic SMF -> Mozart musical-event normalization."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import argparse
import json
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from midi_smf import MidiValidationError, validate_smf


BEAT_GRID = 1.0 / 16.0
PPQ_DEFAULT = 480


@dataclass(frozen=True)
class NormalizedNote:
    start_beat: float
    duration_beats: float
    note: int
    velocity: int
    channel: int


@dataclass(frozen=True)
class NormalizedControl:
    start_beat: float
    controller: int
    value: int
    channel: int


@dataclass(frozen=True)
class TempoEvent:
    beat: float
    bpm: float


@dataclass(frozen=True)
class TimeSignatureEvent:
    beat: float
    numerator: int
    denominator: int


@dataclass(frozen=True)
class NormalizedMidi:
    source_format: int
    source_tracks: int
    source_division: int
    ppq: int
    notes: tuple[NormalizedNote, ...]
    controls: tuple[NormalizedControl, ...]
    tempo_events: tuple[TempoEvent, ...]
    time_signatures: tuple[TimeSignatureEvent, ...]
    length_beats: float
    length_bars: int
    dropped_unmatched_note_offs: int
    dropped_unclosed_notes: int

    def to_json(self) -> dict:
        return {
            "schema_version": 1,
            "source": {
                "format": self.source_format,
                "tracks": self.source_tracks,
                "division": self.source_division,
                "ppq": self.ppq,
            },
            "notes": [asdict(item) for item in self.notes],
            "controls": [asdict(item) for item in self.controls],
            "tempo_events": [asdict(item) for item in self.tempo_events],
            "time_signatures": [asdict(item) for item in self.time_signatures],
            "length_beats": self.length_beats,
            "length_bars": self.length_bars,
            "diagnostics": {
                "dropped_unmatched_note_offs": self.dropped_unmatched_note_offs,
                "dropped_unclosed_notes": self.dropped_unclosed_notes,
            },
        }


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
    for _ in range(4):
        if offset >= len(data):
            raise MidiValidationError("truncated variable-length quantity")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            return value, offset
    raise MidiValidationError("variable-length quantity exceeds four bytes")


def _quantize_steps(ticks: int, ppq: int) -> int:
    value = ticks * 16.0 / ppq
    return math.floor(value + 0.5)


def _ticks_to_beat(ticks: int, ppq: int) -> float:
    return _quantize_steps(ticks, ppq) / 16.0


def _parse_track_events(
    track: bytes,
    track_index: int,
) -> list[tuple[int, int, int, bytes, int]]:
    """Return (absolute_tick, track_index, order, raw_status_payload, type)."""
    events: list[tuple[int, int, int, bytes, int]] = []
    offset = 0
    absolute_tick = 0
    running_status: int | None = None
    order = 0

    while offset < len(track):
        delta, offset = _read_vlq(track, offset)
        absolute_tick += delta
        if offset >= len(track):
            raise MidiValidationError(f"track {track_index}: truncated event")

        status = track[offset]
        if status < 0x80:
            if running_status is None:
                raise MidiValidationError(
                    f"track {track_index}: data byte without running status"
                )
            status = running_status
        else:
            offset += 1

        if 0x80 <= status <= 0xEF:
            message_type = status >> 4
            data_count = 1 if message_type in (0xC, 0xD) else 2
            end = offset + data_count
            if end > len(track):
                raise MidiValidationError(
                    f"track {track_index}: truncated channel event"
                )
            payload = bytes((status,)) + bytes(track[offset:end])
            for byte in track[offset:end]:
                if byte & 0x80:
                    raise MidiValidationError(
                        f"track {track_index}: channel data byte has status bit set"
                    )
            offset = end
            running_status = status
            events.append((absolute_tick, track_index, order, payload, 0))
            order += 1
            continue

        running_status = None

        if status == 0xFF:
            if offset >= len(track):
                raise MidiValidationError(f"track {track_index}: missing meta type")
            meta_type = track[offset]
            offset += 1
            length, offset = _read_vlq(track, offset)
            end = offset + length
            if end > len(track):
                raise MidiValidationError(
                    f"track {track_index}: truncated meta payload"
                )
            payload = bytes((0xFF, meta_type)) + bytes(track[offset:end])
            offset = end
            events.append((absolute_tick, track_index, order, payload, 1))
            order += 1
            if meta_type == 0x2F and length == 0:
                if offset != len(track):
                    raise MidiValidationError(
                        f"track {track_index}: bytes found after End-of-Track"
                    )
                break
            continue

        if status in (0xF0, 0xF7):
            length, offset = _read_vlq(track, offset)
            end = offset + length
            if end > len(track):
                raise MidiValidationError(
                    f"track {track_index}: truncated sysex payload"
                )
            payload = bytes((status,)) + bytes(track[offset:end])
            offset = end
            events.append((absolute_tick, track_index, order, payload, 2))
            order += 1
            continue

        if status in (0xF1, 0xF3):
            if offset >= len(track) or track[offset] & 0x80:
                raise MidiValidationError(
                    f"track {track_index}: invalid system-common payload"
                )
            payload = bytes((status, track[offset]))
            offset += 1
            events.append((absolute_tick, track_index, order, payload, 2))
            order += 1
            continue

        if status == 0xF2:
            if offset + 2 > len(track):
                raise MidiValidationError(
                    f"track {track_index}: truncated song-position event"
                )
            if track[offset] & 0x80 or track[offset + 1] & 0x80:
                raise MidiValidationError(
                    f"track {track_index}: invalid song-position payload"
                )
            payload = bytes((status, track[offset], track[offset + 1]))
            offset += 2
            events.append((absolute_tick, track_index, order, payload, 2))
            order += 1
            continue

        if status == 0xF6:
            events.append((absolute_tick, track_index, order, bytes((status,)), 2))
            order += 1
            continue

        raise MidiValidationError(
            f"track {track_index}: unsupported system status 0x{status:02X}"
        )

    return events


def _load_tracks(data: bytes) -> tuple[int, int, int, list[tuple[int, int, int, bytes, int]]]:
    info = validate_smf(data)
    offset = 14
    all_events: list[tuple[int, int, int, bytes, int]] = []

    for track_index in range(info.track_count):
        track_length = _u32be(data, offset + 4)
        start = offset + 8
        end = start + track_length
        all_events.extend(_parse_track_events(data[start:end], track_index))
        offset = end

    return info.format_type, info.track_count, info.division, all_events


def normalize_smf(
    data: bytes,
    *,
    target_ppq: int = PPQ_DEFAULT,
    quantize: bool = True,
) -> NormalizedMidi:
    if target_ppq <= 0:
        raise ValueError("target_ppq must be positive")

    source_format, track_count, division, events = _load_tracks(data)

    if source_format == 2:
        raise MidiValidationError(
            "MIDI format 2 is not supported by the first deterministic normalizer"
        )
    if division & 0x8000:
        raise MidiValidationError("SMPTE time division is not supported")
    source_ppq = division

    notes: list[NormalizedNote] = []
    controls: list[NormalizedControl] = []
    tempos: list[TempoEvent] = []
    signatures: list[TimeSignatureEvent] = []

    active: dict[tuple[int, int], deque[tuple[int, int, int]]] = defaultdict(deque)
    last_tick = 0
    unmatched_note_offs = 0
    unclosed_notes = 0

    # Track and order remain part of the sorting key so equal-tick events are
    # reproducible even when several tracks share the same timestamp.
    events.sort(key=lambda item: (item[0], item[1], item[2]))

    for absolute_tick, _track, _order, payload, event_kind in events:
        last_tick = max(last_tick, absolute_tick)
        if event_kind != 0:
            if payload[:2] == b"\xff\x51" and len(payload) == 5:
                micros_per_quarter = int.from_bytes(payload[2:], "big")
                if micros_per_quarter > 0:
                    tempos.append(
                        TempoEvent(
                            beat=_ticks_to_beat(absolute_tick, source_ppq),
                            bpm=60_000_000.0 / micros_per_quarter,
                        )
                    )
            elif payload[:2] == b"\xff\x58" and len(payload) == 6:
                numerator = payload[2]
                exponent = payload[3]
                if 1 <= numerator <= 32 and exponent <= 7:
                    signatures.append(
                        TimeSignatureEvent(
                            beat=_ticks_to_beat(absolute_tick, source_ppq),
                            numerator=numerator,
                            denominator=2**exponent,
                        )
                    )
            continue

        status = payload[0]
        message_type = status >> 4
        channel = status & 0x0F
        data1 = payload[1]
        data2 = payload[2] if len(payload) == 3 else None

        if message_type == 0x9 and data2 is not None and data2 > 0:
            active[(channel, data1)].append(
                (absolute_tick, data2, channel)
            )
            continue

        if message_type in (0x8, 0x9):
            if not active[(channel, data1)]:
                unmatched_note_offs += 1
                continue
            start_tick, velocity, note_channel = active[(channel, data1)].popleft()
            start_steps = _quantize_steps(start_tick, source_ppq) if quantize else start_tick
            end_steps = _quantize_steps(absolute_tick, source_ppq) if quantize else absolute_tick
            duration_steps = end_steps - start_steps
            if quantize and duration_steps <= 0:
                duration_steps = 1
            if not quantize and duration_steps <= 0:
                unmatched_note_offs += 1
                continue

            notes.append(
                NormalizedNote(
                    start_beat=start_steps / 16.0 if quantize else start_steps / source_ppq,
                    duration_beats=(
                        duration_steps / 16.0
                        if quantize
                        else duration_steps / source_ppq
                    ),
                    note=data1,
                    velocity=velocity,
                    channel=note_channel,
                )
            )
            continue

        if message_type == 0xB and data2 is not None:
            controls.append(
                NormalizedControl(
                    start_beat=(
                        _ticks_to_beat(absolute_tick, source_ppq)
                        if quantize
                        else absolute_tick / source_ppq
                    ),
                    controller=data1,
                    value=data2,
                    channel=channel,
                )
            )

    for queue in active.values():
        unclosed_notes += len(queue)

    notes.sort(
        key=lambda item: (
            item.start_beat,
            item.channel,
            item.note,
            item.duration_beats,
            item.velocity,
        )
    )
    controls.sort(
        key=lambda item: (
            item.start_beat,
            item.channel,
            item.controller,
            item.value,
        )
    )

    tempo_map = {}
    for event in tempos:
        tempo_map[event.beat] = event
    signature_map = {}
    for event in signatures:
        signature_map[event.beat] = event

    tempos = [tempo_map[key] for key in sorted(tempo_map)]
    signatures = [signature_map[key] for key in sorted(signature_map)]

    length_beats = max(
        [0.0, _ticks_to_beat(last_tick, source_ppq)]
        + [item.start_beat + item.duration_beats for item in notes]
        + [item.start_beat for item in controls]
    )
    length_bars = max(1, math.ceil(length_beats / 4.0))

    return NormalizedMidi(
        source_format=source_format,
        source_tracks=track_count,
        source_division=division,
        ppq=target_ppq,
        notes=tuple(notes),
        controls=tuple(controls),
        tempo_events=tuple(tempos),
        time_signatures=tuple(signatures),
        length_beats=length_beats,
        length_bars=length_bars,
        dropped_unmatched_note_offs=unmatched_note_offs,
        dropped_unclosed_notes=unclosed_notes,
    )


def normalize_file(path: Path) -> NormalizedMidi:
    try:
        return normalize_smf(path.read_bytes())
    except OSError as exc:
        raise MidiValidationError(f"cannot read {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("midi_file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        normalized = normalize_file(args.midi_file)
    except (MidiValidationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(
        normalized.to_json(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
        print(f"PASS: wrote normalized MIDI to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
