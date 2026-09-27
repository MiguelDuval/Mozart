# ADR-0002 — Compact local music-generation model

## Status

Accepted — 2026-09-26.

## Decision

Mozart will use a **compact, purpose-built local symbolic-MIDI Transformer** as its production AI music generator.

Target profile:

- approximately **30–60 million parameters**;
- **int8** deployment target;
- offline/on-device inference;
- 4–16 bar generation as the primary use case;
- polyphonic and multi-voice capable;
- conditioning for genre/subgenre, mood/energy, key/scale, tempo context, density, polyphony, pitch range, rhythmic character and instrument/role;
- deterministic post-validation by Mozart;
- no AI execution in Link timing, scheduler, MIDI callbacks or audio callbacks.

The architecture is inspired by proven symbolic-music approaches such as FIGARO/REMI-style event representations, but Mozart will **not ship third-party pretrained weights by default**. Production weights should be trained/curated for Mozart under a provenance and licensing process suitable for commercial distribution.

## Why this choice

This is the intended balance between:

- musical variety and model capacity;
- Android memory/CPU budget;
- implementation complexity;
- offline operation;
- deterministic realtime behavior;
- future commercial distribution.

A much smaller RNN would be easier to deploy but gives less headroom for style and structural variation. A 1B+ language-model-based MIDI generator is intentionally out of scope for the baseline because it adds substantial memory, packaging and optimization cost.

## Runtime boundary

```
UI / GenerationRequest
        |
        v
LocalMusicModel
        |
        v
PatternProposal
        |
        v
Mozart validation / harmony / constraints
        |
        v
Pattern
        |
        v
Link-aligned scheduler
        |
        v
AMidi
```

The scheduler must remain fully operational if the model is unavailable, busy, loading or disabled.

## Model/runtime technology

The first Android deployment target is **LiteRT**, using its native Android/C++ path. LiteRT provides on-device Android inference and current APIs for CPU/GPU/NPU execution.

The exact LiteRT package/revision will be pinned when the first model artifact is integrated. The model format and runtime must remain behind a narrow Mozart interface so a runtime replacement does not affect the musical domain.

## Commercial-safety policy

Mozart must maintain a provenance record for:

1. source code/license of the model implementation;
2. license of every training/validation dataset;
3. provenance and license of model weights;
4. modifications and preprocessing;
5. attribution obligations;
6. any restrictions on commercial redistribution.

Third-party pretrained checkpoints with non-commercial restrictions are not production dependencies.

Potential training sources may include datasets with permissive commercial-compatible licenses, for example CC BY 4.0 MIDI collections whose provenance is documented. Candidate sources are not automatically approved: each dataset must pass the project's provenance audit before use.

## Training strategy

Do not train the final model directly on unverified internet MIDI.

The training pipeline will:

1. ingest only approved MIDI sources;
2. record per-source provenance and license metadata;
3. normalize MIDI into a compact event representation;
4. derive musical attributes used for conditioning;
5. create train/validation/test splits without leakage;
6. train a compact Transformer;
7. evaluate musical validity, diversity and conditioning adherence;
8. quantize to int8;
9. benchmark Android inference and memory use;
10. package only the approved model artifact and required notices.

Style labels should initially be represented as **controlled tags** (genre/subgenre/mood/rhythm/instrument) rather than requiring an on-device general-purpose language model.

## Non-goals

- No 1B+ LLM in the baseline app.
- No network requirement for generation.
- No note-by-note realtime neural inference.
- No direct AI-to-MIDI hardware output without validation.
- No dependency on a cloud AI provider for basic generation.
