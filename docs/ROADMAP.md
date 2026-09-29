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
- [x] MIDI IN receive queue (bounded native queue + stream parser).
- [x] Android MIDI IN receiver adapter.
- [x] Explicit MIDI IN source selection UI.
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
- [x] Kick/snare/hat-style accompaniment patterns.
- [x] Bass accompaniment.
- [x] Simple arpeggio role.
- [x] Step density.
- [x] Accent.
- [x] Probability.
- [x] Ratchet.
- [x] Swing.
- [x] MIDI scheduler.
- [x] MicroFreak external validation.

## Stage 4 — Harmony
- [x] Scale model.
- [x] Key/Scale context service with explicit source selection (Manual / Audio).
- [x] Manual Key/Scale UI control.
- [x] Stateless chroma-to-Key/Scale estimator core (Major / Natural Minor).
- [x] Local/offline microphone key/scale detector integration.
- [x] Audio detector confidence/stability/hysteresis policy.
- [x] Performer override from Audio back to Manual.
- [x] Chord model.
- [x] Chord progression generator.
- [x] Bass generator.
- [x] Arpeggiator.
- [x] Voice leading.
- [ ] Key/scale detection from MIDI input (deferred; MIDI-IN remains optional infrastructure).

## Stage 5 — Performance
- [x] Scene/pattern switching.
- [x] Quantized pattern launch.
- [x] Live mutation.
- [x] Note repeat.
- [x] Controller mappings.
- [x] Macro controls.

## Stage 6 — Audio preview
- [ ] Oboe integration.
- [ ] Metronome.
- [ ] Preview instrument.
- [ ] Latency diagnostics.
- [ ] Realtime-safe audio graph.

## Stage 7 — Local AI music generation
Decision: compact **30–60M parameter symbolic-MIDI Transformer**, int8, offline/on-device.

- [x] Define GenerationRequest / PatternProposal model contract.
- [x] Add local model provider interface.
- [x] Add model event vocabulary/tokenization contract.
- [x] Pin LiteRT 2.2.0 C++ SDK and add reproducible checksum-verified fetch path.
- [x] Freeze runtime-neutral symbolic token ABI and document model-dependent ABI fields.
- [ ] Freeze production model tensor ABI.
- [ ] Add LiteRT integration behind the provider boundary.
- [ ] Add model loading/eviction lifecycle.
- [x] Add controlled style vocabulary foundation (genre/style slugs and deterministic default conditioning profiles).
- [x] Define runtime-neutral substyle/mood/rhythm/role conditioning vocabulary.
- [x] Add universal model catalog/backend selection boundary for commercial and private experimental models.
- [x] Define permanent Experimental Model Lab boundary (external model files stay outside repository/release artifacts).
- [x] Add Android debug-only Experimental Model Lab selector UI.
- [x] Connect Lab selection to native ModelCatalog selection state.
- [ ] Connect selected model to actual native generation backend execution.
- [x] Add debug-only ONNX Runtime inspection for external model tensor ABI.
- [x] Keep ONNX Runtime out of the commercial release dependency set via debug-only packaging.
- [x] Define licensed-data provenance manifest schema and CI validation.
- [x] Add strict Standard MIDI File structural validation for the training pipeline.
- [x] Add deterministic SMF → Mozart musical-event normalization (PPQ/1-16 beat quantization, note pairing, CC and timing metadata).
- [x] Make normalized musical bar counts meter-aware for 3/4, 4/4 and other supported signatures.
- [x] Add Python training-side implementation of the frozen 512-token ABI with golden vectors.
- [x] Cross-check the frozen token ABI from native C++ tests.
- [x] Build split-ready training examples with explicit source identity.
- [x] Build deterministic bounded JSONL training shards and baseline corpus statistics.
- [x] Add per-example musical quality statistics and deterministic corpus QA/rejection reporting.
- [ ] Add concrete external-runtime inference adapters (ONNX and/or LiteRT).
- [ ] Bind conditioning fields to the production model's tensor representation after the model ABI is frozen.
- [ ] Build licensed-data provenance manifest.
- [ ] Build MIDI normalization and training dataset pipeline.
- [ ] Train first compact model.
- [ ] Add conditioning controls.
- [x] Add deterministic validation/post-processing.
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
