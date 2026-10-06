# Mozart Testing Strategy

## Test pyramid

### Unit tests
Fast host-native tests for pure C++:

- MIDI message encoding/validation;
- beat math;
- quantization;
- Euclidean rhythm;
- probability with fixed seeds;
- scales/chords;
- pattern mutation;
- serialization.

### Integration tests
Run on Android/JNI boundaries:

- application lifecycle;
- MIDI enumeration;
- endpoint selection;
- scheduler;
- Link clock;
- persistence.

### Emulator smoke tests
Run in GitHub Actions:

1. install APK;
2. start activity;
3. verify landscape;
4. verify main controls exist;
5. verify generator can create deterministic state through a test entry point;
6. verify save/load round trip;
7. capture logcat on failure.

### Physical tests
The emulator cannot prove:

- USB MIDI electrical/driver behavior;
- external hardware timing;
- controller-specific quirks;
- real-world routing;
- audible synchronization.

Those remain physical tests.

## Test determinism

Every random generator accepts a seed.

Unit tests must use fixed seeds.

Tests must assert data, not visual impressions.

## Timing tests

Timing tests report:

- scheduled beat;
- resolved host time;
- actual send time when measurable;
- late-event count;
- maximum lateness;
- jitter statistics.

The first stage should measure before it tries to optimize.

## Failure evidence

On Android test failure, collect:

- logcat;
- package/activity;
- emulator API;
- commit SHA;
- test step name.

## Acceptance vocabulary

- PASS — tested and observed.
- PARTIAL — some layers tested.
- UNPROVEN — code exists but test evidence is missing.
- BLOCKED — test infrastructure prevents execution.

## Current physical validation evidence

As of 2026-09-29, the latest Android debug APK was physically exercised on the primary Android test device.

User-reported result:
- 7 of the 8 manual acceptance scenarios completed successfully.
- The MIDI IN scenario was not run and remains **UNPROVEN**.
- The tested scenarios covered application/UI reachability, MIDI OUT/diagnostic note, Ableton Link operation, tempo following, Key/Scale behavior, accompaniment roles, and performance controls.
- This evidence is manual physical validation, not a substitute for automated CI or future soak/timing measurements.

The next MIDI IN test should be recorded separately once an actual MIDI source/controller is available.

## Timing telemetry

The realtime scheduler remains responsible only for musical beat/timestamp resolution, while the bounded MIDI send queue records the moment the transport boundary is reached.

The telemetry snapshot reports:

- scheduled MIDI message count;
- accepted/enqueued message count;
- transport send attempts and successful/failed sends;
- dispatches that reached the transport after their scheduled timestamp;
- maximum dispatch lateness;
- interval jitter computed from successive scheduled versus observed transport-dispatch intervals;
- the most recently scheduled musical beat.

The observed send timestamp is the monotonic timestamp at the start of the transport send() call. For Android AMidi this is **not** a measurement of the physical USB wire time or audible MIDI output time; those still require hardware instrumentation/physical testing.

Telemetry uses atomic counters and does not add filesystem, network, allocation, or blocking-I/O work to the scheduler or MIDI send path.
