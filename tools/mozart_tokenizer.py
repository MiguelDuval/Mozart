#!/usr/bin/env python3
"""Python implementation of Mozart's frozen 512-token MIDI event ABI."""

from __future__ import annotations

from dataclasses import dataclass
import math


PAD = 0
BOS = 1
EOS = 2

CHANNEL_BASE = 16
NOTE_BASE = 32
VELOCITY_BASE = 160
TIME_SHIFT_BASE = 192
DURATION_BASE = 256
CONTROLLER_BASE = 352
CONTROL_VALUE_BASE = 480

VOCABULARY_ID = "mozart-midi-events-v1"
VOCABULARY_SIZE = 512
BEAT_GRID = 1.0 / 16.0
MAX_TIME_SHIFT_STEPS = 64
MAX_DURATION_STEPS = 96


@dataclass(frozen=True)
class TokenizedEvent:
    tokens: tuple[int, ...]


def _bin32(value: int) -> int:
    if not 0 <= value <= 127:
        raise ValueError("MIDI value must be 0..127")
    return max(1, min(32, (value * 32 + 126) // 127))


def _step_from_beat(beat: float) -> int:
    if not math.isfinite(beat) or beat < 0.0:
        raise ValueError("beat must be finite and non-negative")
    value = beat / BEAT_GRID
    if value > (2**63 - 1):
        raise ValueError("beat exceeds token time range")
    return int(math.floor(value + 0.5))


def _duration_steps(duration: float) -> int:
    if not math.isfinite(duration) or duration <= 0.0:
        raise ValueError("duration must be finite and positive")
    steps = int(math.floor(duration / BEAT_GRID + 0.5))
    if not 1 <= steps <= MAX_DURATION_STEPS:
        raise ValueError("duration exceeds frozen Mozart token range")
    return steps


def _channel_token(channel: int) -> int:
    if not 0 <= channel <= 15:
        raise ValueError("channel must be 0..15")
    return CHANNEL_BASE + channel


def _note_token(note: int) -> int:
    if not 0 <= note <= 127:
        raise ValueError("note must be 0..127")
    return NOTE_BASE + note


def _controller_token(controller: int) -> int:
    if not 0 <= controller <= 127:
        raise ValueError("controller must be 0..127")
    return CONTROLLER_BASE + controller


def _velocity_token(value: int) -> int:
    return VELOCITY_BASE + _bin32(value) - 1


def _control_value_token(value: int) -> int:
    return CONTROL_VALUE_BASE + _bin32(value) - 1


def _time_shift_tokens(delta_steps: int) -> list[int]:
    if delta_steps < 0:
        raise ValueError("time cannot move backwards")
    output: list[int] = []
    while delta_steps:
        chunk = min(delta_steps, MAX_TIME_SHIFT_STEPS)
        output.append(TIME_SHIFT_BASE + chunk - 1)
        delta_steps -= chunk
    return output


def encode(
    notes: list[dict],
    controls: list[dict],
    *,
    max_tokens: int = 16_384,
) -> TokenizedEvent:
    """Encode normalized Mozart note/control records deterministically.

    Records must use the same fields emitted by tools/midi_normalize.py.
    At equal beat positions, notes are emitted before control events, matching
    the ordering of src/generation/MidiEventTokenizer.h.
    """

    if max_tokens < 2:
        raise ValueError("max_tokens must be >= 2")

    items: list[tuple[int, int, bool, dict]] = []

    for order, event in enumerate(notes):
        items.append(
            (
                _step_from_beat(float(event["start_beat"])),
                order,
                True,
                event,
            )
        )

    note_count = len(items)
    for order, event in enumerate(controls):
        items.append(
            (
                _step_from_beat(float(event["start_beat"])),
                note_count + order,
                False,
                event,
            )
        )

    items.sort(key=lambda item: (item[0], 0 if item[2] else 1, item[1]))

    tokens: list[int] = [BOS]
    current_steps = 0
    current_channel: int | None = None

    def push(token: int) -> None:
        tokens.append(token)
        if len(tokens) > max_tokens:
            raise ValueError("encoded token stream exceeds max_tokens")

    for start_steps, _order, is_note, event in items:
        if start_steps < current_steps:
            raise ValueError("event time moved backwards")

        for token in _time_shift_tokens(start_steps - current_steps):
            push(token)
        current_steps = start_steps

        channel = int(event["channel"])
        if current_channel is None or channel != current_channel:
            push(_channel_token(channel))
            current_channel = channel

        if is_note:
            push(_note_token(int(event["note"])))
            push(_velocity_token(int(event["velocity"])))
            push(_duration_steps(float(event["duration_beats"])) + DURATION_BASE - 1)
        else:
            push(_controller_token(int(event["controller"])))
            push(_control_value_token(int(event["value"])))

    push(EOS)
    return TokenizedEvent(tuple(tokens))
