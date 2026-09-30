# Mozart Model ABI

## Status

This document freezes the **runtime-neutral** model contract that already exists in Mozart code.

It intentionally does **not** claim that the final LiteRT tensor ABI is frozen. Tensor names, exact shapes, cache tensors and quantization parameters remain model/export dependent and are frozen only after the production model is selected.

## Frozen symbolic token contract

Source of truth:

- `src/generation/MidiEventVocabulary.h`
- `src/generation/MidiEventTokenizer.h`
- `src/generation/MidiEventDetokenizer.h`

The current vocabulary is exactly **512 tokens**:

| Range / token | Meaning |
|---|---|
| 0 | PAD |
| 1 | BOS |
| 2 | EOS |
| 16–31 | channel 0–15 |
| 32–159 | MIDI note 0–127 |
| 160–191 | velocity bins 1–32 |
| 192–255 | time-shift bins 1–64 |
| 256–351 | duration bins 1–96 |
| 352–479 | controller 0–127 |
| 480–511 | controller-value bins 1–32 |

The internal C++ token type is `std::uint16_t`.

The musical grid is **1/16 beat** by default.

## Conditioning vocabulary

The runtime-neutral generation request now carries four explicit control axes in addition to the primary style:

- substyle: `generic`, `techno`, `dark_techno`, `hard_techno`, `trap`, `dark_trap`, `custom`;
- mood: `neutral`, `driving`, `dark`, `aggressive`, `hypnotic`, `tense`, `atmospheric`, `custom`;
- rhythm: `straight`, `syncopated`, `swing`, `half_time`, `double_time`, `broken`, `custom`;
- role: `bass`, `arpeggio`, `chords`, `lead`, `drums`, `percussion`, `texture`, `custom`.

The conditioning vocabulary ID is `mozart-conditioning-v1`.

These tags are a model-independent contract. They do not prescribe how a future checkpoint encodes them into tensors. That mapping remains part of the model-dependent ABI and must be frozen from the actual export.

## Serialization semantics

A generated pattern is represented as an ordered token stream:

```
BOS
  [time-shift]
  CHANNEL
  NOTE VELOCITY DURATION
  [time-shift]
  CHANNEL
  CONTROLLER VALUE
  ...
EOS
```

Channel state is persistent until another channel token appears.

Time shifts advance the absolute musical cursor.

Note duration is encoded independently from time shift.

Controller values are quantized to 32 bins.

Velocity is quantized to 32 bins.

The tokenizer is deterministic: identical `PatternProposal` inputs produce identical token streams.

## Safety boundaries

The current detokenizer rejects:

- PAD/BOS/EOS tokens in invalid positions;
- unknown or out-of-range tokens;
- note data without an initialized channel;
- incomplete note/controller records;
- excessive cumulative time shift;
- excessive event counts;
- malformed event ordering.

The provider path then applies `PatternProposalValidator`, which additionally enforces:

- requested bar length;
- MIDI ranges;
- key/scale projection;
- pitch range;
- density;
- polyphony;
- duplicate canonicalization.

Therefore model output is never treated as executable MIDI bytes.

## Model-runtime boundary

The planned runtime-neutral path is:

```
GenerationRequest
    -> model input encoder
    -> inference backend
    -> token IDs
    -> MidiEventDetokenizer
    -> PatternProposalValidator
    -> PatternProposal
```

The LiteRT implementation belongs only in the inference backend.

The backend may own:

- model loading;
- tensor allocation;
- quantized inference;
- sampling;
- worker-thread execution;
- cancellation/resource lifecycle.

The backend must not own:

- Ableton Link;
- musical scheduling;
- MIDI transport;
- Android UI;
- realtime audio callbacks.

## Model-dependent fields still open

These must be frozen against the actual production checkpoint/export:

- LiteRT signature/key names;
- input tensor dtype;
- input sequence tensor shape;
- output tensor dtype;
- output/logit shape;
- KV-cache representation, if any;
- quantization scales/zero-points;
- maximum context length;
- maximum generated token count;
- sampling strategy and temperature policy;
- model checksum;
- model file format/export revision.

These values must be recorded in a versioned model manifest beside the model artifact.

## Compatibility rule

A model is compatible with Mozart only when:

1. it emits IDs in the frozen 512-token vocabulary;
2. those IDs are accepted by the strict detokenizer;
3. the resulting proposal passes the existing validator;
4. the model manifest explicitly matches the model runtime implementation.

Changing the token vocabulary is a **format version change**, not a silent model swap.

## Current implementation state

The project currently has:

- deterministic local generator;
- tokenizer/detokenizer contract;
- provider interface;
- strict validation;
- LiteRT 2.2.0 SDK preparation;
- experimental ONNX Runtime 1.30.0 adapter behind TokenInferenceBackend;
- runtime-neutral conditioning vocabulary for style, substyle, mood, rhythm and role.

The project does **not** yet have:

- a production checkpoint;
- a model manifest;
- a LiteRT model backend;
- bundled model weights.

That separation is intentional.
