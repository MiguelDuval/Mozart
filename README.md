# Mozart

**Mozart** is a personal Android music instrument for MIDI generation, accompaniment and synchronization.

The project is designed for live use with external MIDI hardware and electronic-music workflows. The first architecture milestone is intentionally small:

**musical input/control → deterministic MIDI generation → Ableton Link timing → Android MIDI output**

Audio preview and richer engine capabilities are added behind clean interfaces so that MIDI timing remains reliable and testable.

## Current status

The repository is being bootstrapped from an empty project.

The authoritative project rules are in:

- `AGENTS.md`
- `docs/PROJECT_MASTER_PROMPT.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/TESTING.md`
- `docs/DEPENDENCIES.md`

## Design priorities

1. Deterministic timing.
2. Reliable MIDI I/O.
3. Hardware-first operation.
4. No avoidable realtime allocations or blocking work.
5. Small, testable vertical slices.
6. Local/deterministic generation first; optional AI assistance behind a non-realtime provider boundary.
7. Landscape-first Android UI.
8. Every meaningful feature backed by automated tests where practical.

## Technology baseline

- Android
- C++20 native core
- Android MIDI / AMidi
- Ableton Link 4.0
- Oboe 1.10.2
- JUCE 9.0.2
- Tracktion Engine 3.2.0

The exact pinned source revisions and licensing notes are recorded in `docs/DEPENDENCIES.md`.

## Development model

`main` is the stable reference.

Experimental work belongs on focused feature branches.

Every meaningful change should end with a build, automated tests, CI verification, and a clear statement of what is and is not physically verified.
