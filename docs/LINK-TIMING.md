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

## Timing telemetry

The scheduler now exposes a diagnostic telemetry snapshot without changing its timing model.

For each scheduled MIDI message, Mozart records the musical beat and the resolved monotonic host timestamp. When the bounded MIDI send queue dispatches that message to the transport, it records the monotonic time at the start of the send() call.

From those points the runtime can report scheduling throughput, enqueue acceptance, transport failures, dispatches that were already late at the transport boundary, maximum lateness, and interval jitter. Jitter is derived from successive scheduled intervals versus successive observed transport-dispatch intervals, rather than from UI polling cadence.

This is intentionally a **transport-boundary measurement**, not a claim about the exact instant a USB MIDI byte reaches external hardware. Physical timing remains a separate acceptance layer.

The telemetry state is atomic and bounded: it introduces no blocking I/O, network work, or unbounded event history into the scheduler path.
