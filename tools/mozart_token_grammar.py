"""Shared Python mirror of the frozen Mozart MIDI token grammar.

The canonical runtime decoder lives with the symbolic MIDI contract. This module
keeps the development trainer/evaluators on the same token-state rules without
changing the exported model tensor ABI.
"""

from __future__ import annotations

from typing import Sequence


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
VOCABULARY_SIZE = 512


def has_channel_token(tokens: Sequence[int]) -> bool:
    return any(
        CHANNEL_BASE <= token < NOTE_BASE
        for token in tokens
    )


def allowed_next_token_ranges(
    tokens: Sequence[int],
) -> tuple[tuple[int, int], ...]:
    """Return half-open token ranges allowed after the current prefix."""
    if not tokens:
        return ()

    last = int(tokens[-1])

    if last == BOS:
        return (
            (CHANNEL_BASE, NOTE_BASE),
            (TIME_SHIFT_BASE, DURATION_BASE),
        )

    if NOTE_BASE <= last < VELOCITY_BASE:
        return ((VELOCITY_BASE, TIME_SHIFT_BASE),)

    if VELOCITY_BASE <= last < TIME_SHIFT_BASE:
        return ((DURATION_BASE, CONTROLLER_BASE),)

    if CONTROLLER_BASE <= last < CONTROL_VALUE_BASE:
        return ((CONTROL_VALUE_BASE, VOCABULARY_SIZE),)

    if DURATION_BASE <= last < CONTROLLER_BASE:
        return (
            (EOS, EOS + 1),
            (CHANNEL_BASE, NOTE_BASE),
            (TIME_SHIFT_BASE, DURATION_BASE),
            (NOTE_BASE, VELOCITY_BASE),
            (CONTROLLER_BASE, CONTROL_VALUE_BASE),
        )

    if CONTROL_VALUE_BASE <= last < VOCABULARY_SIZE:
        return (
            (EOS, EOS + 1),
            (CHANNEL_BASE, NOTE_BASE),
            (TIME_SHIFT_BASE, DURATION_BASE),
            (NOTE_BASE, VELOCITY_BASE),
            (CONTROLLER_BASE, CONTROL_VALUE_BASE),
        )

    if TIME_SHIFT_BASE <= last < DURATION_BASE:
        if has_channel_token(tokens):
            return (
                (CHANNEL_BASE, NOTE_BASE),
                (TIME_SHIFT_BASE, DURATION_BASE),
                (NOTE_BASE, VELOCITY_BASE),
                (CONTROLLER_BASE, CONTROL_VALUE_BASE),
            )
        return (
            (CHANNEL_BASE, NOTE_BASE),
            (TIME_SHIFT_BASE, DURATION_BASE),
        )

    if CHANNEL_BASE <= last < NOTE_BASE:
        return (
            (NOTE_BASE, VELOCITY_BASE),
            (CONTROLLER_BASE, CONTROL_VALUE_BASE),
        )

    return ()


def is_allowed_next_token(
    tokens: Sequence[int],
    next_token: int,
) -> bool:
    if not tokens or not 0 <= int(next_token) < VOCABULARY_SIZE:
        return False

    value = int(next_token)
    return any(
        start <= value < end
        for start, end in allowed_next_token_ranges(tokens)
    )


def allowed_next_tokens(tokens: Sequence[int]) -> tuple[int, ...]:
    values: list[int] = []
    for start, end in allowed_next_token_ranges(tokens):
        values.extend(range(start, end))
    return tuple(values)
