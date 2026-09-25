# AI Generation Contract

## Principle

AI is an assistant to the musical engine, never its clock.

The app must work with AI disabled.

## Provider boundary

```
interface MusicGenerationProvider {
    generate(request) -> PatternProposal
}
```

The provider returns structured data.

It does not return arbitrary executable MIDI bytes.

## Request

A request can include:

- style;
- BPM range;
- key/scale;
- chord progression;
- bar count;
- density;
- syncopation;
- energy;
- instrument role;
- seed;
- constraints.

## Response

The response should contain:

- notes;
- durations;
- velocity ranges;
- controllers only when requested;
- metadata;
- provider diagnostics.

## Validation

Before a proposal enters the musical model:

1. parse schema;
2. limit total events;
3. clamp ranges;
4. reject invalid timestamps;
5. reject unsupported channels;
6. enforce musical bounds;
7. normalize duplicates;
8. assign deterministic fallback values.

## NIM

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
