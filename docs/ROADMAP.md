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
- [x] Android MIDI device enumeration.
- [x] Deterministic USB-MIDI endpoint selection.
- [x] Identify/select Arturia MicroFreak without accidentally selecting unrelated devices.
- [ ] MIDI IN receive queue.
- [x] MIDI OUT queue.
- [x] Timestamp preservation.
- [ ] Virtual/test MIDI adapter.
- [ ] MicroFreak physical MIDI test record.

## Stage 2 — Ableton Link accompanist clock
- [x] Link 4.0 wrapper.
- [x] Link enable/disable runtime control.
- [x] Session tempo / beat / phase snapshot API.
- [ ] Android Link runtime/session validation.
- [ ] Quantized launch.
- [x] Follow-session policy.
- [x] Scheduler look-ahead.
- [ ] Link test suite.

## Stage 3 — First useful accompanist
- [x] Deterministic seeded rhythm generator.
- [ ] Kick/snare/hat-style accompaniment patterns.
- [x] Bass accompaniment.
- [ ] Simple arpeggio role.
- [ ] Step density.
- [ ] Accent.
- [ ] Probability.
- [ ] Ratchet.
- [ ] Swing.
- [x] MIDI scheduler.
- [ ] MicroFreak external validation.

## Stage 4 — Harmony
- [x] Scale model.
- [ ] Key/Scale context service with explicit source selection (Manual / Audio).
- [x] Manual Key/Scale control.
- [ ] Local/offline microphone key/scale detector integration.
- [ ] Audio detector confidence/stability/hysteresis policy.
- [ ] Performer override from Audio back to Manual.
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
