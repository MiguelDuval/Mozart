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
