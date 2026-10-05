# Bootstrap Checklist

This document records the initial project state before the first MIDI implementation slice.

## Repository
- [x] `main` contains the stable documented foundation.
- [x] `feature/midi-foundation` is the active implementation branch.
- [x] Architecture and dependency contracts exist.

## Build
- [x] Android Gradle project exists.
- [x] C++20 native target exists.
- [x] Host-native C++ tests exist.
- [x] Android emulator smoke test is defined.
- [x] Direct APK artifact is configured with `archive: false`.

## First implementation slice
The next functional slice is Android MIDI discovery and endpoint selection.

It must prove:

```
Android MidiManager
    -> device discovery
    -> deterministic device selection
    -> transport-neutral MIDI boundary
```

No musical generation or AI calls belong in this slice.
