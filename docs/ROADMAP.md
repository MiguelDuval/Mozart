# Mozart Roadmap

## Execution order and gates

The project follows this dependency order for the core instrument:

**Stage 0 → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5 → Stage 7 (Local AI) → Stage 9 (Persistence) → Stage 10 (Hardening).**

Stage 6 (Audio preview) is **independent of the Local AI gate**. It may proceed before, after, or alongside Stage 7 when it is useful, but audio must not delay local AI integration.

The Local AI stage may have small preparatory/documentation work earlier when required, but production model integration starts only after these gates are satisfied:

- Stage 2: Link timing and scheduler are stable.
- Stage 3: deterministic accompaniment and MIDI output are physically validated.
- Stage 4: key/scale and harmonic context are sufficiently stable for conditioning.
- Stage 5: basic pattern/performance workflow exists so generated patterns have a real product destination.

Local AI must never be introduced by modifying the realtime clock/scheduler path. Its output enters the existing musical-domain/pattern path and then uses the already-validated scheduler.


## Stage 0 — Foundation
- [x] Empty repository converted into a documented project.
- [x] Android/C++ build skeleton.
- [x] Native unit-test harness.
- [x] Direct APK artifact.
- [x] Emulator smoke-test path.
- [x] Dependency policy and pins.
- [ ] First green CI on the bootstrap commit.

## Stage 1 — MIDI / MicroFreak transport
- [x] Android MIDI device enumeration.
- [x] Deterministic USB-MIDI endpoint selection.
- [x] Identify/select Arturia MicroFreak without accidentally selecting unrelated devices.
- [ ] MIDI IN receive queue.
- [x] MIDI OUT queue.
- [x] Timestamp preservation.
- [ ] Virtual/test MIDI adapter.
- [x] MicroFreak physical MIDI test.

## Stage 2 — Ableton Link accompanist clock
- [x] Link 4.0 wrapper.
- [x] Link enable/disable runtime control.
- [x] Session tempo / beat / phase snapshot API.
- [x] Android Link runtime validation.
- [x] Android Link peer/session validation.
- [x] Quantized launch.
- [x] Follow-session policy.
- [x] Scheduler look-ahead.
- [x] Continuous accompaniment across Link tempo changes.
- [x] Link test suite.

## Stage 3 — First useful accompanist
Current vertical slice: Manual F# minor context → selectable deterministic bass/arpeggio accompaniment → Link rolling scheduler → bounded MIDI OUT queue → Android AMidi boundary. Physical MicroFreak MIDI receipt and Link tempo-following playback are verified.
- [x] Deterministic seeded rhythm generator.
- [ ] Kick/snare/hat-style accompaniment patterns.
- [x] Bass accompaniment.
- [x] Simple arpeggio role.
- [x] Step density.
- [ ] Accent.
- [ ] Probability.
- [ ] Ratchet.
- [ ] Swing.
- [x] MIDI scheduler.
- [x] MicroFreak external validation.

## Stage 4 — Harmony
- [x] Scale model.
- [ ] Key/Scale context service with explicit source selection (Manual / Audio).
- [x] Manual Key/Scale UI control.
- [ ] Local/offline microphone key/scale detector integration.
- [ ] Audio detector confidence/stability/hysteresis policy.
- [ ] Performer override from Audio back to Manual.
- [ ] Chord model.
- [ ] Chord progression generator.
- [x] Bass generator.
- [x] Arpeggiator.
- [ ] Voice leading.
- [ ] Key/scale detection from MIDI input.

## Stage 5 — Performance
- [ ] Scene/pattern switching.
- [ ] Quantized pattern launch.
- [ ] Live mutation.
- [ ] Note repeat.
- [ ] Controller mappings.
- [ ] Macro controls.

## Stage 6 — Audio preview
- [ ] Oboe integration.
- [ ] Metronome.
- [ ] Preview instrument.
- [ ] Latency diagnostics.
- [ ] Realtime-safe audio graph.

## Stage 7 — Local AI music generation
Decision: compact **30–60M parameter symbolic-MIDI Transformer**, int8, offline/on-device.

- [ ] Define GenerationRequest / PatternProposal model contract.
- [ ] Add local model provider interface.
- [ ] Add model event vocabulary/tokenization contract.
- [ ] Add LiteRT integration behind the provider boundary.
- [ ] Add model loading/eviction lifecycle.
- [ ] Add controlled style vocabulary (genre/subgenre/mood/rhythm/role).
- [ ] Build licensed-data provenance manifest.
- [ ] Build MIDI normalization and training dataset pipeline.
- [ ] Train first compact model.
- [ ] Add conditioning controls.
- [ ] Add deterministic validation/post-processing.
- [ ] Add generation latency/memory benchmarks on Android.
- [ ] Quantize and package production model artifact.
- [ ] Verify commercial redistribution requirements for final model and data.

## Stage 8 — Optional AI providers
- [ ] NVIDIA NIM provider.
- [ ] Optional text → controlled musical request parser.
- [ ] Higher-level arrangement / mutation suggestions.
- [ ] Never allow NIM/network operations into realtime scheduling.

## Stage 9 — Persistence
- [ ] Session format v1.
- [ ] Pattern library.
- [ ] Presets.
- [ ] Mappings.
- [ ] Migration tests.
- [ ] Backup/export.

## Stage 10 — Hardening
- [ ] Soak tests.
- [ ] Disconnect/reconnect tests.
- [ ] Sleep/resume tests.
- [ ] Timing telemetry.
- [ ] Crash diagnostics.
- [ ] Release build.

## Stage 11 — Optional expansion
- [ ] MIDI 2.0 / UMP.
- [ ] External audio I/O.
- [ ] Link Audio if genuinely useful.
- [ ] Multi-device workflows.
