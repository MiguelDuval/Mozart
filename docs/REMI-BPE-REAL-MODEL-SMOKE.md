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
5. Replays the exact generated token IDs once through Mozart's production RemiBpePatternProvider (substituting only the inference boundary) to verify the real paired tokenizer loads and the full stream is accepted or atomically rejected by production rules. It separately compiles and exercises Mozart's production BpeTokenizer, RemiDecoderConfig, RemiEventAdapter, proposal validator, and REMI-to-Link converter. It checks every generated ID, scans all 20,000 vocabulary entries for independent decodability, verifies PAD/BOS/EOS, and records whether the actual ONNX output can be decoded into a valid typed proposal and converted to a Link proposal. No missing EOS or unsupported Program event is synthesized/dropped to force a pass.
6. Uploads only a small checksum/provenance report, including machine-readable C++ tokenizer, typed-proposal, and Link-conversion diagnostics. The checkpoint, tokenizer and ONNX graph are deliberately excluded from the artifact and repository.

This is not yet an Android/device playback test, and it does not establish musical quality for electronic music. The production path still requires a model trained for Mozart's broad electronic-music objective plus Android-side real-artifact inference and hardware playback verification.

## Running it

The workflow is triggered when its own file, the exporter, the smoke helper or C++ artifact-smoke test changes on feature/remi-bpe-link-integration; it can also be started manually from GitHub Actions via “REMI/BPE Real Checkpoint Export Smoke → Run workflow”.


## Verified real-artifact result (2026-10-28)

The pinned-checkpoint run [40784702458](https://github.com/MiguelDuval/Mozart/actions/runs/40784702458), exact source SHA `5fcf5b04a4df4de3eb0e3ab41cce4a2f77bbc544`, passed ONNX export/parity, manifest validation, autoregressive inference and the C++ integration diagnostic. The uploaded 1,021-byte report records:
- Full tokenizer: 20,000/20,000 vocabulary entries independently decodable; zero generated token IDs dropped.
- Generated output: 65 IDs including BOS (64 new tokens); no EOS at the smoke cap, so the full stream is not production-provider-ready. The smoke also runs those unchanged IDs through the production C++ provider, which must fail closed with an empty proposal rather than emit partial notes.
- Diagnostic-only complete-event prefix: 20 IDs, 10 typed notes, zero program changes, zero control changes; REMI-to-Link conversion and the shared request validator both accepted it.
- The remaining 45 generated IDs were omitted only from this explicit diagnostic-prefix check. Production decoding is unchanged and still refuses unterminated/invalid full streams.


## Production-provider replay verified (2026-10-28)

The real-checkpoint workflow at exact source SHA `ddcdb9d6833bcc1c5106efad4976c4861e367e95` passed: [run 40786409627](https://github.com/MiguelDuval/Mozart/actions/runs/40786409627), report artifact [12859137903](https://github.com/MiguelDuval/Mozart/actions/runs/40786409627/artifacts/12859137903).

In addition to the earlier C++ tokenizer/adapter/Link checks, the test replayed the exact 65 generated IDs through Mozart's production `RemiBpePatternProvider` using a fake only at the model inference boundary:
- Provider initialization loaded the exact paired 20k tokenizer.
- Inference boundary was called once with the real output unchanged.
- Full output was rejected with `REMI/BPE token stream must be BOS/EOS terminated`; provider returned zero notes and zero controls. This is the expected fail-closed result because the model did not emit EOS.
- Separately, a 20-token complete-event prefix decoded to 10 notes and passed the existing REMI-to-Link converter and shared request-aware validator. This prefix-only diagnostic is never marked provider-ready.
- All 20,000 tokenizer entries remained individually decodable and no generated IDs were dropped. Model weights, tokenizer JSON and ONNX graph were not uploaded.

The real-model workflow's path filters now include the production C++ token decoder, adapter, provider, converter, proposal validator, and their direct musical dependencies, so changes to those implementations re-run the real artifact test rather than relying only on synthetic fixtures.
