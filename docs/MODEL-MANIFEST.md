# Mozart Production Model Manifest

## Purpose

This document defines the **machine-checkable information that must accompany the production local symbolic-MIDI model** before LiteRT runtime wiring is enabled.

It is a template, not the final ABI. Values marked `<FROZEN>` must come from the actual exported production checkpoint. Do not invent tensor names, shapes, quantization parameters, cache tensors, or sampling values.

The manifest is part of the model artifact contract. A model is not releasable when its weights exist without a matching manifest.

## Status

`template-not-frozen`

The runtime-neutral symbolic token ABI is already frozen in `docs/MODEL-ABI.md`. The model-dependent tensor ABI remains open until the production checkpoint/export is selected and inspected.

## Required manifest fields

The final manifest must contain these fields:

```text
manifest_schema_version
model_id
model_revision
model_file
model_format
model_sha256
distribution_class
vocabulary_id
vocabulary_size
context_length_tokens
max_generated_tokens

inputs[]
outputs[]
kv_cache[]
quantization
conditioning
decoding
provenance
licenses
```

Each tensor entry must record at least:

```text
name
dtype
shape
layout
role
```

The final manifest must additionally record the quantization scale/zero-point representation for every quantized tensor that requires it.

The machine-checkable JSON template is `docs/model-manifest.example.json`. Validate it with `tools/validate_model_manifest.py`. Template manifests may contain `<FROZEN>` placeholders; frozen manifests may not.

## Reference shape

The following is intentionally schematic:

```yaml
manifest_schema_version: <FROZEN>
model_id: <FROZEN>
model_revision: <FROZEN>
model_file: <FROZEN>
model_format: <FROZEN>
model_sha256: <FROZEN>
distribution_class: commercial | private_experimental

vocabulary_id: mozart-midi-events-v1
vocabulary_size: 512

context_length_tokens: <FROZEN>
max_generated_tokens: <FROZEN>

inputs:
  - name: <FROZEN>
    dtype: <FROZEN>
    shape: [<FROZEN>]
    layout: <FROZEN>
    role: token_ids_or_conditioning

outputs:
  - name: <FROZEN>
    dtype: <FROZEN>
    shape: [<FROZEN>]
    layout: <FROZEN>
    role: token_scores_or_token_ids

kv_cache:
  enabled: <FROZEN>
  tensors:
    - name: <FROZEN>
      dtype: <FROZEN>
      shape: [<FROZEN>]
      layout: <FROZEN>

quantization:
  scheme: <FROZEN>
  activations: <FROZEN>
  weights: <FROZEN>
  scales: <FROZEN>
  zero_points: <FROZEN>

conditioning:
  style_family: <FROZEN>
  substyle: <FROZEN>
  mood: <FROZEN>
  rhythm: <FROZEN>
  role: <FROZEN>
  key_scale: <FROZEN>
  chords: <FROZEN>
  density: <FROZEN>
  energy: <FROZEN>
  syncopation: <FROZEN>
  swing: <FROZEN>
  variation: <FROZEN>
  seed: <FROZEN>

decoding:
  strategy: <FROZEN>
  temperature: <FROZEN>
  top_k: <FROZEN>
  top_p: <FROZEN>
  seed_policy: <FROZEN>

provenance:
  training_source: <FROZEN>
  dataset_manifest: <FROZEN>
  preprocessing_revision: <FROZEN>

licenses:
  implementation: <FROZEN>
  model_weights: <FROZEN>
  training_data: <FROZEN>
  redistribution: <FROZEN>
```

The exact field representation may change when the export toolchain is selected, but the information itself is mandatory.

## Freeze procedure

Freeze the manifest only after the production checkpoint has been selected.

1. Inspect the exported model and identify every input/output/cache tensor.
2. Record exact tensor names, dtypes, shapes and layouts.
3. Record quantization parameters and the model file SHA-256.
4. Record the maximum context and generation lengths.
5. Freeze the tokenizer vocabulary ID and ensure the model emits only the 512-token Mozart vocabulary.
6. Record the conditioning representation and decoding/sampling policy.
7. Record training-data provenance and all implementation/weights/data redistribution licenses.
8. Run `tools/validate_model_manifest.py` and its regression test before enabling the LiteRT backend.
9. Run native/provider tests plus an Android inference smoke test with the exact model artifact.

## Distribution compatibility gate

A manifest with distribution_class `private_experimental` must never be used as evidence that the model may be redistributed. The classification records Mozart's packaging intent; the model's actual license remains authoritative.

A production/commercial manifest must use `commercial` only after the implementation, weights, training-data and redistribution audit is complete.

## Runtime compatibility gates

The LiteRT backend must reject a model when:

- the manifest schema version is unsupported;
- the vocabulary ID or size does not match Mozart's frozen token ABI;
- a required tensor is missing;
- tensor dtype or shape differs from the manifest;
- quantization metadata is missing or inconsistent;
- the model checksum does not match the packaged artifact;
- the model's output cannot be consumed by the strict tokenizer/detokenizer contract.

A model mismatch must surface as `Unavailable` or `Failed`; it must never silently select another model or bypass `PatternProposalValidator`.

## Relationship to existing documents

- `docs/MODEL-ABI.md` defines the runtime-neutral 512-token contract.
- `docs/LITERT.md` defines the pinned 2.2.0 SDK boundary and integration gates.
- `docs/AI-GENERATION.md` defines provider/threading/commercial-safety rules.
- This document defines the production-model manifest handoff needed before the LiteRT backend is enabled.
