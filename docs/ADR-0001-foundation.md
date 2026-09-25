# ADR-0001 — MIDI-first Android instrument

## Decision

Mozart begins as a MIDI-first Android instrument with a C++20 musical core.

Android MIDI is the transport boundary, Ableton Link is the shared clock, and deterministic generators are the source of musical events.

Audio and AI are supporting subsystems rather than the first dependency chain.

## Why

This produces the shortest path to a useful personal instrument.

MIDI output can be tested independently of audio rendering.

Ableton Link provides the shared musical timing model.

A deterministic generator makes tests repeatable and keeps the instrument functional offline.

AI can be layered on later without compromising timing.

## Consequences

The first versions will not be a complete groovebox or DAW.

The project will invest heavily in scheduling, event validation and testability before visual complexity.
