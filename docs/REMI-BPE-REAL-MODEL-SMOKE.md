# Real REMI/BPE exporter integration smoke

This is a **technical integration fixture**, not Mozart's target musical model. The pinned checkpoint is a public GPT-2 REMI-BPE model trained on MAESTRO classical piano. It is used to validate that Mozart can load a complete learned BPE tokenizer, export its causal LM to ONNX, run a short autoregressive inference, and decode the exact generated token IDs through Mozart's C++ BPE tokenizer.

## Pinned input

- Repository: NathanFradet/Maestro-REMI-bpe20k
- Immutable revision: ec0960a622b46d77ed59fdd09de422aa205ca6a4
- Declared model type: GPT-2 causal LM, GPT2LMHeadModel
- Declared vocabulary: 20,000
- The public model card declares Apache-2.0 and identifies MAESTRO classical-piano training data. This does not make it a broad EDM checkpoint.

## What the workflow verifies

1. Downloads the configuration, tokenizer and weights at the immutable revision into the runner's external Hugging Face cache. It does not write weights into Git.
2. Requires the checkpoint's vocabulary and special-token IDs to match the learned MidiTok BPE tokenizer.
3. Exports a private temporary ONNX graph and checks eager-vs-ONNX logits at several sequence lengths.
4. Runs a short autoregressive ONNX generation loop.
5. Compiles the same BpeTokenizer.cpp used by Mozart and verifies that every ID emitted by the real ONNX graph is inside the learned vocabulary and maps to REMI semantic names without drops; it also compares PAD/BOS/EOS against model config.
6. Uploads only a small checksum/provenance report. The checkpoint, tokenizer and ONNX graph are deliberately excluded from the artifact and repository.

This is not yet an Android/device playback test, and it does not establish musical quality for electronic music. The production path still requires a model trained for Mozart's broad electronic-music objective plus Android-side real-artifact inference and hardware playback verification.

## Running it

The workflow is triggered when its own file, the exporter, the smoke helper or C++ artifact-smoke test changes on feature/remi-bpe-link-integration; it can also be started manually from GitHub Actions via “REMI/BPE Real Checkpoint Export Smoke → Run workflow”.
