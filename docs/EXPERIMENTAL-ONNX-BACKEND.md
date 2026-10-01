# Experimental ONNX Backend

## Purpose

Mozart has a concrete external-runtime inference adapter behind
TokenInferenceBackend.

This path is private experimental infrastructure. Model artifacts stay outside
Git and outside distributed APK/AAB artifacts.

## Runtime path

```text
Experimental Model Lab
        |
        v
app-private model.properties
        |
        v
ModelCatalog
        |
        v
OnnxTokenInferenceBackend
        |
        v
Android JNI bridge
        |
        v
ONNX Runtime 1.30.0 (debug build)
        |
        v
ONNX logits
        |
        v
greedy Mozart token IDs
        |
        v
MidiEventDetokenizer
        |
        v
PatternProposalValidator
```

GenerationService invokes the backend only on its dedicated worker thread. A generation request is also tagged with the model-selection epoch; if the user changes or clears the selection before completion, the result is discarded instead of entering the scheduler.

## Compatibility gate

The first adapter accepts only ONNX models that already emit Mozart's frozen
512-token vocabulary and the exact development Transformer conditioning ABI:

- vocabulary ID: mozart-midi-events-v1;
- vocabulary size: 512;
- token input: `input_ids` as int64 `[1, sequence]`;
- style inputs: `style_id`, `substyle_id`, `mood_id`, `rhythm_id`, and `role_id`
  as int64 `[1]` tensors;
- performance conditioning: `performance_controls` as float32 `[1, 5]`, ordered
  as density, energy, syncopation, swing, variation;
- output tensor: `logits`;
- BOS=1 and EOS=2;
- bounded context and generation length.

The Android bridge converts the portable GenerationRequest JSON into those exact
six conditioning tensors and sends them on every autoregressive `session.run`
alongside the current `input_ids`. Key/scale and chord progression remain part
of the portable request contract but are not sent to this exported graph because
they are not among its seven ONNX inputs.

After the ONNX session is created, the Java bridge compares the manifest tensor
contract with the actual session input/output tensor metadata for all seven
inputs plus the output. A missing or incompatible conditioning tensor is
reported as a failed experimental model and inference does not continue.

## External vocabulary policy

The adapter does not silently reinterpret third-party tokenizer IDs.

AuraMIDI-v1 is an external technical candidate. Its published model card
reports a 48.60M-parameter causal decoder-only Transformer and a published ONNX
artifact, but its vocabulary is 10,000 MidiTok REMI IDs. That means it must fail
the first Mozart adapter's 512-token ABI gate. A future Aura-specific adapter
would need an explicit, tested event-semantic translation layer rather than an
ID-range remap.

The published card also describes training from Lakh Clean MIDI, MAESTRO and
additional multi-genre stems. That provenance remains an experimental review
item and is not, by itself, production redistribution approval.

## Manifest extension

Private experimental ONNX manifests may add:

```json
{
  "runtime": {
    "backend": "onnxruntime",
    "input_name": "input_ids",
    "output_name": "logits",
    "input_dtype": "int64",
    "token_mode": "mozart_ids",
    "external_vocabulary_size": 512,
    "context_length_tokens": 1024,
    "max_generated_tokens": 512,
    "bos_token_id": 1,
    "eos_token_id": 2,
    "allow_unhashed_experimental": true
  }
}
```

The machine-readable manifest validator checks that the runtime block refers to
declared input/output tensors and stays within the root context/generation
limits.

## Android debug flow

The Experimental Model Lab discovers:

```text
<app-private>/experimental-models/<model-id>/
  model.properties
  model.onnx
  model.manifest.json
```

Selecting a model creates an ONNX backend instance and registers it with
ModelCatalog. The debug UI exposes a non-realtime "RUN AI GENERATION TEST"
control. The request is queued asynchronously and the UI polls for a completed
GenerationResult without blocking the main thread.

The current first adapter forwards the full GenerationRequest as a bridge
payload, starts autoregression from BOS, and encodes the exact seven-input
development graph contract before each inference step. The five categorical
fields are converted to int64 batch scalars; density, energy, syncopation, swing,
and variation are converted to one float32 `[1,5]` batch tensor. No network or
LLM dependency is introduced into this path.

## Fail-closed behavior

The adapter rejects:

- missing artifact or manifest;
- invalid manifest schema/runtime block;
- unsafe model paths from descriptor files;
- wrong vocabulary ID/size;
- wrong input dtype;
- missing or inconsistent tensor names/shapes;
- mismatched concrete SHA-256;
- wrong BOS/EOS;
- missing output logits;
- output tensors that cannot be interpreted;
- token IDs outside Mozart's 512-token vocabulary;
- generation without EOS inside the configured bound.

No rejected model bypasses MidiEventDetokenizer or PatternProposalValidator.

## Production gate

This adapter is not a production model integration.

Production still requires:

1. a Mozart-compatible checkpoint;
2. frozen tensor ABI;
3. frozen quantization and decoding policy;
4. audited training-data provenance;
5. verified implementation/weights/data redistribution rights;
6. concrete model checksum and manifest;
7. real-device memory and latency validation.

No model weights are committed by this adapter.
