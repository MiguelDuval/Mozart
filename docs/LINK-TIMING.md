# Ableton Link Timing Contract

## Product policy

Mozart follows the shared Link session by default.

It is not a technical master/slave system.

## Required concepts

- local tempo;
- session tempo;
- beat;
- phase;
- quantum;
- host time;
- start/stop intent;
- connection state.

## Initial quantum

Use a default quantum of 4 beats (one 4/4 bar).

Expose it as a product setting later.

## Scheduling

The scheduler should work ahead of the current time.

Conceptually:

```
currentHostTime
    ↓
capture Link session state
    ↓
currentBeat
    ↓
generate/lookup events in [currentBeat, currentBeat + lookAhead]
    ↓
convert beat → host time
    ↓
queue MIDI timestamps
```

The scheduler must tolerate tempo changes without corrupting event order.

## Thread rule

When Link state is queried from a realtime callback, use the realtime-safe capture path.

Application/UI code should use the non-realtime session-state path.

Do not mix state mutations across threads casually.

## Link validation

The future Link test suite should cover:

- join an existing session;
- follow tempo;
- preserve local state when no peer exists;
- beat/phase continuity;
- quantized launch;
- optional Start/Stop Sync;
- disconnect/reconnect.

Ableton's documented Link test plan is the external reference.
