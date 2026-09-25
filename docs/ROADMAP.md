# Mozart Roadmap

## Stage 0 — Foundation
- [x] Empty repository converted into a documented project.
- [x] Android/C++ build skeleton.
- [x] Native unit-test harness.
- [x] Direct APK artifact.
- [x] Emulator smoke-test path.
- [x] Dependency policy and pins.
- [ ] First green CI on the bootstrap commit.

## Stage 1 — MIDI
- [ ] Android MIDI device enumeration.
- [ ] Deterministic endpoint selection.
- [ ] MIDI IN receive queue.
- [ ] MIDI OUT queue.
- [ ] Timestamp preservation.
- [ ] Virtual/test MIDI adapter.
- [ ] Physical MIDI test record.

## Stage 2 — Link clock
- [ ] Link 4.0 wrapper.
- [ ] Link enable/disable.
- [ ] Session tempo readout.
- [ ] Beat/phase conversion.
- [ ] Quantized launch.
- [ ] Follow-session policy.
- [ ] Link test suite.

## Stage 3 — First instrument
- [ ] Deterministic seeded rhythm generator.
- [ ] Step density.
- [ ] Accent.
- [ ] Probability.
- [ ] Ratchet.
- [ ] Swing.
- [ ] MIDI scheduler.
- [ ] External synth validation.

## Stage 4 — Harmony
- [ ] Scale model.
- [ ] Chord model.
- [ ] Chord progression generator.
- [ ] Bass generator.
- [ ] Arpeggiator.
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

## Stage 7 — AI
- [ ] Provider interface.
- [ ] Structured schema.
- [ ] Local deterministic fallback.
- [ ] NVIDIA NIM provider.
- [ ] Response validation.
- [ ] Prompt templates.

## Stage 8 — Persistence
- [ ] Session format v1.
- [ ] Pattern library.
- [ ] Presets.
- [ ] Mappings.
- [ ] Migration tests.
- [ ] Backup/export.

## Stage 9 — Hardening
- [ ] Soak tests.
- [ ] Disconnect/reconnect tests.
- [ ] Sleep/resume tests.
- [ ] Timing telemetry.
- [ ] Crash diagnostics.
- [ ] Release build.

## Stage 10 — Optional expansion
- [ ] MIDI 2.0 / UMP.
- [ ] External audio I/O.
- [ ] Link Audio if genuinely useful.
- [ ] Multi-device workflows.
