# Mozart Roadmap

## Stage 0 — Foundation
- [x] Empty repository converted into a documented project.
- [x] Android/C++ build skeleton.
- [x] Native unit-test harness.
- [x] Direct APK artifact.
- [x] Emulator smoke-test path.
- [x] Dependency policy and pins.
- [ ] First green CI on the bootstrap commit.

## Stage 1 — MIDI / MicroFreak transport
- [ ] Android MIDI device enumeration.
- [ ] Deterministic USB-MIDI endpoint selection.
- [ ] Identify/select Arturia MicroFreak without accidentally selecting unrelated devices.
- [ ] MIDI IN receive queue.
- [ ] MIDI OUT queue.
- [ ] Timestamp preservation.
- [ ] Virtual/test MIDI adapter.
- [ ] MicroFreak physical MIDI test record.

## Stage 2 — Ableton Link accompanist clock
- [ ] Link 4.0 wrapper.
- [ ] Link enable/disable.
- [ ] Session tempo readout.
- [ ] Beat/phase conversion.
- [ ] Quantized launch.
- [ ] Follow-session policy.
- [ ] Scheduler look-ahead.
- [ ] Link test suite.

## Stage 3 — First useful accompanist
- [ ] Deterministic seeded rhythm generator.
- [ ] Kick/snare/hat-style accompaniment patterns.
- [ ] Bass accompaniment.
- [ ] Simple arpeggio role.
- [ ] Step density.
- [ ] Accent.
- [ ] Probability.
- [ ] Ratchet.
- [ ] Swing.
- [ ] MIDI scheduler.
- [ ] MicroFreak external validation.

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

## Stage 7 — AI-assisted accompaniment
- [ ] Provider interface.
- [ ] Structured schema.
- [ ] Local deterministic fallback.
- [ ] NVIDIA NIM provider.
- [ ] Response validation.
- [ ] Prompt templates.
- [ ] Convert NIM musical suggestions into deterministic accompaniment plans.
- [ ] Never allow NIM/network operations into realtime scheduling.

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
