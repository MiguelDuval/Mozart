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

A local model provider and future remote providers use the same boundary.

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

Controlled style vocabulary should initially use explicit tags such as electronic → techno → dark techno or hip-hop → trap → dark trap. A future text parser may map natural-language requests into these tags, but a general-purpose LLM is not required for the baseline generator.

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

## Threading and realtime rules

Local model loading and inference run on a non-realtime worker.

Never call local or remote AI from:

- audio callbacks;
- MIDI receive callbacks;
- scheduler send loops;
- Link timing callbacks.

Generation must be cancellable/bounded where practical and must never block transport progress.

## Android runtime

The first deployment target is LiteRT behind the provider boundary. The runtime is responsible for model inference; Mozart remains responsible for token/event encoding, validation and final musical rendering.

The exact LiteRT revision is not hard-coded into the domain and will be pinned when integration begins.

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
