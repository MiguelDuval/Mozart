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
