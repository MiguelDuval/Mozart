# LiteRT Integration

## Purpose

This document freezes the first reproducible LiteRT dependency boundary for Mozart.

LiteRT is an **optional local inference runtime**. It is not part of the musical clock, MIDI scheduler, Link callback, MIDI receive callback, or audio callback.

## Pinned SDK

- LiteRT release: **2.2.0**
- C++ SDK artifact: `litert_cc_sdk.zip`
- SHA-256:
  `0aa619d80aef27303ad9c6e3759a20110f77e7b11ade9b68061b8c6e5904b0c6`
- Upstream release: https://github.com/google-ai-edge/LiteRT/releases/tag/v2.2.0
- Official C++ Android integration guidance: https://ai.google.dev/edge/litert/android/cpp

The checksum above is the checksum published for the official v2.2.0 C++ SDK release asset. The model artifact has a separate checksum and provenance record.

## Reproducible fetch

From the repository root:

```bash
bash tools/fetch_litert.sh
```

The script:

1. downloads the pinned C++ SDK when it is not already cached;
2. verifies the exact SHA-256;
3. extracts it to `third_party/litert/`;
4. records `VERSION` and `SHA256` inside the extracted directory.

The extracted SDK is intentionally ignored by Git. Do not commit the SDK contents to the Mozart repository.

## Integration boundary

The existing production design is:

```
GenerationRequest
    -> TokenInferenceBackend
    -> MidiEventToken stream
    -> strict MidiEventDetokenizer
    -> PatternProposalValidator
    -> PatternProposal
    -> deterministic musical rendering
    -> existing scheduler
```

LiteRT belongs only behind `TokenInferenceBackend`.

The provider layer must not:

- call Ableton Link;
- schedule MIDI timestamps;
- access Android UI state;
- write directly to a hardware MIDI port;
- block the scheduler;
- run from an audio or MIDI callback.

Model inference runs on a bounded worker thread. The realtime musical path remains fully functional with LiteRT unavailable.

## Android packaging boundary

The official LiteRT Android C++ integration uses the LiteRT C++ SDK together with the LiteRT runtime library. The runtime library should be supplied through the Android dependency mechanism described by the upstream documentation rather than copied into the Mozart source tree.

Mozart should therefore keep two concerns separate:

- **SDK headers/CMake integration**: reproducibly fetched by `tools/fetch_litert.sh`;
- **Android runtime library packaging**: added only when the concrete model/runtime interface is implemented and tested.

Do not enable a global `MOZART_ENABLE_LITERT` build path until the model tensor contract is frozen. The first production build should fail closed when the SDK/runtime prerequisites are missing rather than silently falling back to a different runtime.

## Model gate before code integration

Before wiring LiteRT into `LocalNeuralPatternProvider`, freeze and document:

- input tensor names, types and shapes;
- output tensor names, types and shapes;
- token vocabulary version;
- maximum token sequence length;
- quantization scheme;
- model input conditioning format;
- model output sampling/decoding policy;
- model checksum;
- training-data provenance;
- implementation, weight and data licenses.

This prevents the runtime API from becoming coupled to a temporary model experiment.

## Validation gates

The LiteRT integration is accepted only when all of the following hold:

1. the native core still builds and its existing tests pass;
2. the provider returns `Unavailable` when the runtime/model is absent;
3. invalid model output cannot reach MIDI transport;
4. inference never runs on the scheduler or audio callback;
5. generated patterns use the existing `PatternProposal` validation path;
6. deterministic fallback generation continues to work with LiteRT disabled;
7. Android memory and generation latency are measured on a real device.

## Dependency policy

LiteRT upgrades are dedicated dependency changes.

Never replace this pin with a moving branch or an unversioned Maven coordinate. When upgrading:

1. record the new upstream release;
2. record the new immutable artifact checksum;
3. rebuild the Android app;
4. run native tests;
5. run the provider contract tests;
6. run an Android inference smoke test with the production model;
7. update the model/runtime compatibility note.

## Current status

This repository has **LiteRT dependency preparation only**.

The production model is not bundled yet, and no LiteRT inference call is enabled in the application. That is intentional: the model ABI and token contract must be frozen before runtime code is added.
