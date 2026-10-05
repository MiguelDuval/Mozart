# AI Generation Contract

## Principle

AI is an assistant to the musical engine, never its clock.

The app must work with AI disabled.

## Production local model

Mozart's selected production direction is a **compact local symbolic-MIDI Transformer**:

- target size: approximately 30–60M parameters;
- int8 deployment target;
- offline/on-device inference;
- primary generation length: 4–16 bars;
- polyphonic and multi-voice capable;
- controlled generation rather than free-form unconstrained MIDI;
- own Mozart model weights for production distribution.

The design is informed by open symbolic-music research such as FIGARO and REMI-style event representations. Mozart does not depend on third-party non-commercial pretrained checkpoints.

## Provider boundary

```
interface MusicGenerationProvider {
    generate(request) -> PatternProposal
}
```

The provider returns structured data.

It does not return arbitrary executable MIDI bytes.

For neural providers the transport-neutral model path is:

```
GenerationRequest
    -> model input encoding
    -> model inference
    -> grammar-constrained token selection
    -> MidiEventToken stream
    -> strict MidiEventDetokenizer
    -> PatternProposalValidator
    -> validated PatternProposal
```

Every provider must apply the same deterministic validation gate before its proposal is accepted by the musical engine. The deterministic local provider uses this same validator, so the offline fallback and the future LiteRT path share the same output contract.

A local model provider and future remote providers use the same boundary.

Mozart also has a permanent Experimental Model Lab boundary. External or non-redistributable checkpoints may be selected for private development through the model catalog, but their artifacts remain outside Git and outside distributed APK/AAB packages. Experimental models use exactly the same token detokenization and PatternProposalValidator gates as production models.

The universal selection path is `modelId -> ModelCatalog -> TokenInferenceBackend`. The backend may use LiteRT, ONNX or another runtime, while the musical engine sees only Mozart's token contract.

The neural provider is split into two responsibilities: a generic `TokenInferenceBackend` owns model-runtime interaction, while `LocalNeuralPatternProvider` owns detokenization and the common Mozart validation gate. LiteRT will implement the backend interface; it must not be embedded into the musical-domain classes.

## Request

Key/scale context should normally come from Mozart's local musical-domain state.

A request can include:

- style family;
- substyle;
- mood/energy;
- BPM range;
- key/scale;
- chord progression;
- bar count;
- density;
- polyphony;
- pitch range;
- syncopation;
- swing;
- instrument/voice role;
- variation;
- seed;
- constraints.

Live performance macros are normalized into the same request contract. Energy maps to the model's energy field; Motion maps to syncopation and variation so the generator becomes more rhythmically active as Motion rises. Motion does not modify Link tempo, beat, phase or scheduler timing.

Controlled style vocabulary should initially use explicit tags such as electronic -> techno -> dark techno or hip-hop -> trap -> dark trap. A future text parser may map natural-language requests into these tags, but a general-purpose LLM is not required for the baseline generator.

## Response

The response should contain:

- notes;
- durations;
- velocity ranges;
- controllers only when requested;
- metadata;
- deterministic seed;
- provider diagnostics.

## Validation

Before a proposal enters the musical model:

1. parse schema;
2. limit total events;
3. clamp ranges;
4. reject invalid timestamps;
5. reject unsupported channels;
6. enforce key/scale and musical bounds;
7. enforce density/polyphony/pitch-range limits;
8. normalize duplicates;
9. assign deterministic fallback values.

Malformed or out-of-contract AI output must never reach the MIDI transport unchanged.

The experimental Android ONNX bridge applies the same frozen Mozart token grammar
while selecting each next token. This is a runtime safety layer, not a substitute
for model quality: the development sequence evaluator deliberately measures the
unconstrained model first, so grammar-constrained decoding cannot hide autoregressive
training failures. PyTorch/ONNX diagnostic comparisons remain based on raw greedy
selection.

The current scheduler handoff intentionally accepts note events only. A proposal
containing control events is rejected at the scheduler boundary until semantic
CC/control scheduling is implemented. The engine must never silently discard a
valid-looking control event produced by a model.

## Integration gate and implementation order

Local AI integration is a later vertical slice, not a prerequisite for the core instrument.

Required order:

1. stabilize Link/scheduler and deterministic accompaniment;
2. stabilize key/scale and harmonic context;
3. stabilize the basic pattern/performance workflow;
4. define the generation contract and event representation;
5. freeze the model tensor/token ABI and pin the LiteRT runtime;
6. integrate the local model on a worker thread;
7. validate/post-process proposals through existing musical-domain constraints;
8. benchmark memory/latency on real Android hardware;
9. expose the first generation controls in the UI.

Audio preview is not a dependency of this sequence.

## LiteRT runtime

The first deployment target is **LiteRT 2.2.0** behind the provider boundary.

The repository contains a reproducible SDK fetch path in `tools/fetch_litert.sh`. The official C++ SDK asset is verified by SHA-256 before extraction. See `docs/LITERT.md`.

The actual LiteRT runtime/model wiring remains gated on the frozen model tensor contract. Do not add LiteRT calls to the scheduler, Link clock, MIDI receive path, or audio callback.

The runtime layer is responsible for tensor inference; Mozart remains responsible for token encoding, event validation and final musical rendering.

## Threading and realtime rules

Local model loading and inference run on a non-realtime worker.

Never call local or remote AI from:

- audio callbacks;
- MIDI receive callbacks;
- scheduler send loops;
- Link timing callbacks.

Generation requests are bounded by the worker queue. Individual backend inference is currently non-cancellable: `stop()` marks the service stopped, invalidates the current lifecycle session, drains queued jobs, and waits for any active inference to return before joining the worker. Backend implementations must therefore return without depending on transport teardown or the generation service itself. This shutdown wait remains off the realtime transport path.

### Scheduler handoff

`GenerationService` returns an asynchronous `GenerationResult` tagged with the
model-selection generation and generation-service lifecycle session captured at
submission time. A result produced for an older model selection or an older service
session is stale and must not be applied to the live musical state.

`MozartRuntime::queueGeneratedResult()` is the guarded application boundary:
it requires a successful result whose `GenerationRequestTicket` still matches the
currently selected model, selection generation, and generation-service lifecycle
session, then hands the already validated `PatternProposal` to the scheduler. This check is outside the realtime
scheduler loop; the scheduler never waits for inference and never performs
network/model work.

The scheduler accepts at most one pending generated proposal and activates it at
a musical boundary. If the pending slot is occupied, a new proposal is rejected
rather than replacing an already scheduled musical decision.


## Android runtime packaging

Keep the LiteRT C++ SDK headers/CMake integration separate from the Android runtime library packaging.

The SDK is intentionally not vendored into Git. The extracted SDK is created locally/CI by `tools/fetch_litert.sh`.

Runtime packaging is added only after the model ABI is frozen and the corresponding Android inference smoke test exists.

## Model manifest

The model-dependent ABI is recorded in a versioned manifest alongside each production model artifact. The repository template is `docs/MODEL-MANIFEST.md`. Experimental model handling and release separation are defined in `docs/EXPERIMENTAL-MODELS.md`.

The manifest is the handoff point between model export and the LiteRT backend. It must be generated from the actual exported model rather than filled with guessed tensor names or shapes.

## Commercial-safety rules

Production Mozart must not ship with a third-party checkpoint whose license restricts commercial use.

For every model artifact we ship, the repository must document:

- implementation/license;
- exact weights or training source;
- dataset provenance;
- preprocessing;
- attribution notices;
- redistribution permissions;
- checksum/version.

Training data will be restricted to sources that pass this project's provenance and commercial-use audit.

## NIM

NVIDIA NIM remains an optional future provider for higher-level musical interpretation or idea generation.

NIM must not replace the local production generator and must not be required for offline operation.

NVIDIA NIM may be used through an OpenAI-compatible HTTP provider abstraction.

Configuration must provide:

- endpoint URL;
- model ID;
- timeout;
- max response size;
- API key reference.

Do not hard-code a model name because available NIM models can change.

Do not call NIM from:

- audio callbacks;
- MIDI receive callbacks;
- scheduler send loops.

## Offline fallback

If AI is unavailable, deterministic generators continue to work.

AI errors must never stop the musical transport.
