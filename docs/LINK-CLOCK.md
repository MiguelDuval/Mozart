# Ableton Link Clock Integration

## Purpose

Mozart uses Ableton Link as its shared musical clock. Link supplies synchronized session timing; it does not supply key or scale information.

The first Link slice exposes only the timing data required by the accompanist:

- Link enabled/disabled state;
- session tempo;
- current beat;
- phase within a quantum;
- peer count / session presence;
- start/stop state;
- monotonic host time corresponding to the snapshot.

The initial Mozart quantum is **4 beats**.

## Wrapper boundary

`src/clock/LinkClock` is the Mozart-facing wrapper around the pinned Ableton Link C++ API.

The rest of Mozart must not include Link headers directly.

The wrapper currently provides an application-thread snapshot:

`captureAppSnapshot()`

This uses Link's application-thread session-state capture API. It is not intended for an audio callback or other hard realtime context.

## Android platform

The pinned Link 4.0 source does not define a dedicated Android platform. For the Android target, Mozart explicitly enables Link's Linux platform implementation because Android's native environment provides the required monotonic clock, POSIX networking and pthread facilities.

This is an integration choice at the platform boundary; it does not make Android code part of the musical domain.

## Scheduler tempo-change policy

The accompaniment scheduler keeps a persistent musical note cursor. A Link tempo change therefore changes only the beat-to-host-time conversion for newly scheduled events; it does not restart the pattern or wait for a new 4-beat quantum.

The scheduler uses a short rolling look-ahead rather than placing a complete bar of future MIDI timestamps into the Android transport at once. This limits the amount of future MIDI that can become stale when another Link peer changes tempo while the pattern is already running.

A late scheduler wake-up does not intentionally drop the current musical step; the event is clamped to the current monotonic host time so the sequence remains continuous. Physical timing quality still requires real-device measurement.

## Accompaniment roles

The first two deterministic roles are:

- **Bass** — low-register seeded eighth-note accompaniment in the selected scale.
- **Arpeggio** — higher-register seeded eighth-note scale arpeggio.

The role selector is intentionally quantized: choosing BASS or ARPEGGIO while playback is running requests the new role, and the scheduler activates it at the next 4-beat bar boundary. The current phrase is never truncated just because the performer changed role.

Both roles use the same Link beat cursor and rolling look-ahead scheduler, so tempo changes affect their timestamps without restarting either sequence.

## Android runtime validation

The debug Android smoke path now validates the Link lifecycle itself:

1. Start the runtime and verify an enabled Link snapshot with the expected default tempo.
2. Capture a second snapshot after one second and verify that the Link beat has advanced rather than remaining static.
3. Stop accompaniment, disable Link, and verify the final snapshot reports `enabled=false`.
4. Keep the diagnostic status visible in the Activity so a physical device can expose the same enabled/playing/peer/tempo/beat/phase state during manual testing.

This validates the local Link runtime path in CI. It does **not** prove multi-device session discovery, peer synchronization, USB-MIDI hardware receipt, or physical timing quality.

## Dependency

Link is pinned to:

`e9a2e414d63f55f1aad158370b007a6fbdc1eeb9`

The Link repository contains an ASIO-standalone submodule, so dependency checkout must initialize submodules recursively.

## Timing rule

Link provides the session tempo and the beat/phase timeline. Mozart's future scheduler will convert musical beat coordinates into host timestamps and keep MIDI transmission in its dedicated transport/send context.

Key/Scale remains independent:

`Link timing + Manual/Audio Key Context -> Accompaniment Generator`
`-> Scheduler -> MIDI transport`

No key/scale value is inferred from Link.
