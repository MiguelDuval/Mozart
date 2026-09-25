# Mozart Architecture

## Layer map

```
Musical intent / context
        |
        v
Accompaniment engine
        |
        v
Pattern / scheduler
        |
        v
Ableton Link clock
        |
        v
Android MIDI transport
        |
        v
USB MIDI
        |
        v
Arturia MicroFreak

Android UI / lifecycle
        |
        v
Platform adapters
  - Android MIDI
  - permissions
  - storage
        |
        v
Transport-neutral MIDI
        |
        +--------------------+
        |                    |
        v                    v
Musical domain <-------- Clock service
        |                    |
        v                    v
Generators              Ableton Link
        |
        v
Scheduler
        |
        v
MIDI output
        |
        v
Arturia MicroFreak / other MIDI synths / DAW
```

Optional paths:

- Audio preview hangs off the scheduler/domain, never the UI.
- AI provider feeds validated proposals into the musical domain.
- Persistence serializes domain/session state.

## Ownership rules

### Android
Owns lifecycle, platform permissions, device enumeration and document APIs.

### MIDI transport
Owns bytes, ports, timestamps, reconnects and platform quirks.

### Clock
Owns conversion between host time and musical beat/phase.

### Key Context
Owns the resolved musical key/scale context used by accompaniment generation.

Key context may come from:
- performer-selected Manual Key/Scale;
- stabilized local Audio Key Detection from microphone input;
- future AI-assisted interpretation as an optional input.

Key Context is musical-domain state. It does not own MIDI timing or transport.

### Domain
Owns music: notes, patterns, scales, chords, scenes and user intent.

### Generator
Owns deterministic pattern creation and mutation.

### Scheduler
Owns when events should leave the process.

### Audio
Owns sample/synth rendering and realtime constraints.

### AI
Owns network/provider interaction only. It never owns timing.

### UI
Owns presentation and commands only.

## Forbidden dependencies

- Domain → Android
- Domain → JUCE UI
- Domain → Android MIDI
- Generator → Android
- Generator → network
- Scheduler → UI
- Audio callback → network/filesystem
- AI provider → scheduler internals
- UI → raw MIDI bytes

## Time representation

Musical objects use beat coordinates.

Transport objects use monotonic host timestamps.

Link is the authority for synchronized session beat/tempo/phase when Link is active.

The scheduler resolves a bounded set of future musical events into timestamped transport events.

## Queue policy

Cross-thread communication should use bounded queues or immutable snapshots.

The transport boundary may copy incoming bytes once.

The scheduler should prepare outgoing events ahead of their send deadline.

## Error policy

Every layer returns explicit errors or state objects.

Do not use silent fallback for device-selection, timing or generation failures.

## Build topology

The initial build deliberately keeps heavy audio dependencies optional so the repository can prove the MIDI core quickly.

Dependencies are pinned and documented before they are enabled in production targets.
