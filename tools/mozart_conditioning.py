#!/usr/bin/env python3
"""Frozen Python mirror of the model-independent Mozart conditioning vocabulary."""

from __future__ import annotations

CONDITIONING_VOCABULARY_ID = "mozart-conditioning-v1"

STYLE_SLUGS = frozenset({
    "electronic",
    "techno",
    "dark_techno",
    "hard_techno",
    "trap",
    "custom",
})

SUBSTYLE_SLUGS = frozenset({
    "generic",
    "techno",
    "dark_techno",
    "hard_techno",
    "trap",
    "dark_trap",
    "custom",
})

MOOD_SLUGS = frozenset({
    "neutral",
    "driving",
    "dark",
    "aggressive",
    "hypnotic",
    "tense",
    "atmospheric",
    "custom",
})

RHYTHM_SLUGS = frozenset({
    "straight",
    "syncopated",
    "swing",
    "half_time",
    "double_time",
    "broken",
    "custom",
})

ROLE_SLUGS = frozenset({
    "bass",
    "arpeggio",
    "chords",
    "lead",
    "drums",
    "percussion",
    "texture",
    "custom",
})

PERFORMANCE_CONTROL_NAMES = (
    "density",
    "energy",
    "syncopation",
    "swing",
    "variation",
)


def validate_performance_controls(
    controls: dict[str, float],
) -> dict[str, float]:
    if not isinstance(controls, dict):
        raise ValueError("performance_controls must be an object")
    normalized: dict[str, float] = {}
    for name in PERFORMANCE_CONTROL_NAMES:
        value = controls.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"performance_controls.{name} must be a number"
            )
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"performance_controls.{name} must be in [0, 1]"
            )
        normalized[name] = value
    return normalized


def derive_performance_controls(
    notes: list[dict],
    length_beats: float,
) -> dict[str, float]:
    """Derive retrospective metrics for QA, never training conditioning labels.

    Training examples must receive performance controls from an independent
    intent/context source so target events cannot leak into conditioning.
    """
    if length_beats <= 0.0:
        raise ValueError("length_beats must be positive")
    if not notes:
        return {name: 0.0 for name in PERFORMANCE_CONTROL_NAMES}
    density = min(1.0, len(notes) / (length_beats * 4.0))
    energy = sum(int(note["velocity"]) for note in notes) / (
        len(notes) * 127.0
    )
    syncopation = sum(
        round(float(note["start_beat"]) * 4.0) % 4 != 0
        for note in notes
    ) / len(notes)
    unique_pitches = len({int(note["note"]) for note in notes})
    variation = min(1.0, max(0.0, (unique_pitches - 1) / 7.0))
    return {
        "density": density,
        "energy": energy,
        "syncopation": syncopation,
        "swing": 0.0,
        "variation": variation,
    }


def validate_conditioning(
    *,
    style: str,
    substyle: str,
    mood: str,
    rhythm: str,
    role: str,
    seed: int,
) -> dict:
    values = {
        "style": (style, STYLE_SLUGS),
        "substyle": (substyle, SUBSTYLE_SLUGS),
        "mood": (mood, MOOD_SLUGS),
        "rhythm": (rhythm, RHYTHM_SLUGS),
        "role": (role, ROLE_SLUGS),
    }

    normalized: dict[str, str | int] = {}
    for name, (value, allowed) in values.items():
        if not isinstance(value, str):
            raise ValueError(f"conditioning.{name} must be a string")
        value = value.strip()
        if value not in allowed:
            raise ValueError(
                f"conditioning.{name} has unsupported slug: {value!r}"
            )
        normalized[name] = value

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("conditioning.seed must be an integer")
    if not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("conditioning.seed must fit uint32")

    normalized["seed"] = seed
    return normalized
