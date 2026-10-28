# REMI/BPE checkpoint compatibility audit

**Status: BLOCKED for the currently published `shikhr/music_maker` artifact pair.** Do not export or run this checkpoint through Mozart's REMI/BPE provider until the trained tokenizer/model vocabulary is recovered and matched.

## Evidence at the inspected revision

The public model card describes a GPT-style model with a 12,000-token vocabulary and a piano-only training set. Its `config.json` at model revision `7528164fe0d4fa2625f1bfc126cc8df62791a429` declares `model_type: mgpt`, `block_size: 1024`, and `vocab_size: 12000`.

The paired public `tokenizer.json` from the same revision declares MidiTok `REMI` (version 3.0.4), pitch range 21–109, position resolutions 8 and 4, and 16 velocity values. In the published raw JSON inspected on 2026-10-28, the serialized structure contains `_vocab_base` with the base event IDs 0–440 and `_vocab_base_byte_to_token`, but no serialized `_model` object/string containing the learned Hugging Face BPE model vocabulary.

That means the public model config says 12,000 output IDs, while the published tokenizer file exposes only the 441-event base vocabulary and does not supply the trained BPE vocabulary/merges required to translate those IDs back into base REMI events. The missing mapping cannot be reconstructed safely from the model weights or from the base vocabulary alone. The repo's exporter deliberately rejects a tokenizer without the serialized `_model`; it must not invent a mapping or reinterpret the first 441 IDs as proof of compatibility.

References:
- [Published model config at the inspected immutable revision](https://huggingface.co/shikhr/music_maker/resolve/7528164fe0d4fa2625f1bfc126cc8df62791a429/config.json)
- [Published tokenizer at the inspected immutable revision](https://huggingface.co/shikhr/music_maker/resolve/7528164fe0d4fa2625f1bfc126cc8df62791a429/tokenizer.json)
- [Model card / usage notes](https://huggingface.co/shikhr/music_maker)

## Runtime protections added

The C++ tokenizer now exposes whether it actually loaded a learned BPE model vocabulary. A plain MidiTok base vocabulary remains inspectable for tooling/tests, but `RemiBpePatternProvider` rejects it before inference. The provider also requires the model manifest's declared output vocabulary size to match the paired tokenizer's learned BPE vocabulary size. Sparse/duplicate vocabulary IDs and non-BPE embedded tokenizer models fail closed.

These checks are exercised by native tests for:
- a valid trained-BPE fixture;
- a base-vocabulary-only MidiTok fixture;
- a 12,000-ID model manifest paired with a different-sized tokenizer;
- strict exporter rejection when `_model` is absent.

## Exit criteria

Before this external checkpoint can be used:
1. Obtain the original trained BPE tokenizer artifact whose vocabulary is exactly aligned with the model's 12,000 logits.
2. Verify the tokenizer and weights are the same training/export pair by immutable revisions and SHA-256 hashes.
3. Run `tools/export_remi_bpe_onnx.py` on the locally held files and preserve its output contract report.
4. Run the resulting model and tokenizer through Android inference smoke tests, then test generated MIDI with physical hardware.

If the original BPE artifact cannot be recovered, this checkpoint is not currently a safe REMI/BPE integration candidate. Continue model development with a tokenizer/model pair whose ABI is complete and reproducible; do not silently substitute the base vocabulary.
