# Key / Scale Context Contract

## Purpose

Mozart needs musical key/scale context independently from Ableton Link so the accompaniment engine can generate notes that belong to the current musical context.

Ableton Link provides synchronized musical timing such as session tempo, beat and phase. **Link does not provide the musical key or scale.**

Mozart therefore has two primary key-context sources for the first usable versions:

1. **Manual Key/Scale**
2. **Audio Key Detection from microphone input**

A future NVIDIA NIM integration may provide an additional intelligent interpretation path, but NIM must remain outside the realtime MIDI/timing path.

## Source A — Manual Key/Scale

The performer can explicitly set the key and scale in Mozart, for example:

- C major
- F# minor
- D dorian

Manual selection is the deterministic fallback and must remain available even when audio analysis or AI is unavailable.

The selected key/scale should be represented as musical-domain state, not as an Android/UI-specific value.

## Source B — Audio Key Detection

Mozart may listen to microphone input and run an offline/local key-detection engine.

Conceptually:

**Microphone → audio analysis → estimated Key/Scale → musical-domain Key Context**

The detector may produce uncertainty or competing candidates. Mozart should therefore treat the result as an estimate rather than unquestionable truth.

The first implementation should support:

- current estimated key;
- scale/mode when the detector can identify it;
- confidence/quality information where available;
- stabilization/hysteresis so short transients do not continuously retune the accompaniment;
- explicit performer override back to Manual Key/Scale.

Audio analysis must not run on the MIDI scheduler's realtime send path and must not require a network connection.

## Key Context Resolution

The accompaniment engine consumes one resolved musical context:

**Manual Key/Scale OR stabilized Audio Key Detection → Key Context → Generator**

For the initial implementation, the performer can choose the active source/mode. Manual mode always remains available as a deterministic fallback.

When Audio mode is active, a practical policy is to update the resolved key only after the detector has produced a stable result for a bounded period or sufficient analysis frames. Exact thresholds should be decided during implementation and physical testing.

Changing key context should be treated as a musical event/state transition, not as a transport-clock event. Ableton Link continues to supply timing independently.

## Future NIM extension

NVIDIA NIM may later receive musical/audio context and contribute a key/scale interpretation or higher-level harmonic suggestion.

NIM must not become a required dependency for key detection, and it must never be called from:

- audio callbacks;
- MIDI receive callbacks;
- scheduler send loops;
- any realtime MIDI timing path.

The local/manual paths must continue to function when NIM is disabled, unavailable, or offline.

## Architectural Relationship

The intended control flow is:

**Ableton Link → BPM / beat / phase**

**Manual Key/Scale ─┐**
**                   ├→ Resolved Key Context → Accompaniment Generator → Scheduler → MIDI**
**Audio Key Detector ─┘**

This separates **time** from **harmony** while keeping both available to the musical engine.
