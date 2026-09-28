# Mozart Local Model Selection

## Purpose

Track external symbolic-MIDI model candidates before Mozart freezes a production checkpoint.

The production target remains a compact 30–60M parameter causal symbolic-MIDI Transformer, deployable locally and quantized for Android.

External checkpoints are now allowed as **private experimental models** through the Experimental Model Lab. This separates technical evaluation from commercial approval: an experimental checkpoint can be tested without becoming a dependency of the distributed Mozart artifact.

This document is a research log, not a release approval. A candidate is not commercially approved merely because its code repository is permissively licensed; the exact model weights, tokenizer, training data and redistribution terms must all pass review.

## Evaluation gates

A candidate must satisfy all of these before becoming a production base:

1. Causal generation architecture suitable for 4–16 bar continuation/generation.
2. Approximately 30–60M parameters, or a documented path to that budget.
3. Symbolic MIDI/event representation that can be adapted to Mozart's frozen 512-token ABI without weakening validation.
4. Export path that can be converted to the selected Android runtime.
5. Deterministic/separable conditioning for style, substyle, mood, rhythm, role and musical context.
6. Weight license permits the intended commercial redistribution.
7. Training-data provenance and downstream redistribution rights are independently acceptable.
8. Exact checkpoint checksum and export metadata can be captured in docs/MODEL-MANIFEST.md.

## Candidates checked on 2026-09-28

### MIDI-GPT / yellow_small

Source:
https://github.com/Metacreation-Lab/MIDI-GPT

Checkpoint:
https://huggingface.co/Metacreation/MIDI-GPT

Observed facts:

- yellow_small-final.safetensors is published as a completed 500k-step checkpoint.
- The checkpoint is approximately 82.5 MB.
- The model family uses a GPT-2-style architecture; the repository documents a 512 hidden dimension, 6 layers and 8 heads for its model configuration.
- The yellow family supports 4- and 8-bar contexts and controls such as note density, polyphony and note duration.
- The GitHub source repository is MIT licensed.
- The Hugging Face model repository is marked cc-by-nc-4.0, so the published pretrained weights are not an acceptable commercial dependency for Mozart without a separate permission/license change.

Status: REJECTED AS A COMMERCIAL WEIGHTS DEPENDENCY.

The architecture and training ideas remain useful references. Mozart may reproduce compatible architecture/training methodology from independently licensed data and code, but must not silently reuse these restricted weights.

Sources:
- https://github.com/Metacreation-Lab/MIDI-GPT/blob/main/LICENSE
- https://github.com/Metacreation-Lab/MIDI-GPT/blob/main/docs/models.md
- https://huggingface.co/Metacreation/MIDI-GPT

### AuraMIDI-v1

Source:
https://huggingface.co/nitrai-research/AuraMIDI-v1

Observed facts:

- Causal decoder-only Transformer.
- 48.60M parameters.
- 12 layers, hidden size 512, feed-forward size 2048.
- 1024-token context.
- 10,000-token MidiTok REMI vocabulary.
- Published PyTorch and ONNX artifacts.
- Model card marks the repository MIT.
- The model card reports training on 19,833 songs from Lakh Clean MIDI, MAESTRO and additional modern multi-genre stems.

Compatibility findings:

- Parameter budget and causal architecture are close to Mozart's target.
- ONNX export is useful evidence that a compact symbolic model can be packaged for mobile/portable inference.
- The 10,000-token REMI vocabulary does not match Mozart's frozen 512-token event ABI.
- The published artifact is not int8; quantization would still be required.
- The additional modern-stem data provenance and redistribution terms have not yet been independently audited for a commercial derivative.

Status: TECHNICAL RESEARCH CANDIDATE, NOT COMMERCIALLY APPROVED.

The most useful path may be to reproduce a similarly sized architecture with Mozart's own tokenizer and a separately audited dataset rather than adapting the published checkpoint.

Source:
https://huggingface.co/nitrai-research/AuraMIDI-v1

### MIDIT checkpoints

Source:
https://huggingface.co/SimoneZanetti00/MIDIT-checkpoints

Observed facts:

- Approximately 42.5M parameters.
- BERT-style masked-language model for symbolic music infilling.
- REMI+ tokenization.
- Hugging Face repository is marked MIT.
- Model card says the weights were trained on the Lakh MIDI Dataset and were released for research purposes.

Compatibility findings:

- Size is within the Mozart target.
- Architecture is masked/infill-oriented rather than a straightforward causal decoder for Mozart's planned autoregressive token stream.
- REMI+ vocabulary/sequence semantics do not match the frozen Mozart 512-token ABI.
- The research purposes wording means commercial redistribution requires clarification before treating these weights as an acceptable dependency.

Status: HOLD FOR LICENSE/ARCHITECTURE CLARIFICATION.

Source:
https://huggingface.co/SimoneZanetti00/MIDIT-checkpoints

## Experimental-model policy

Candidates that are technically useful but fail the current commercial provenance/license gate should be evaluated through the Experimental Model Lab rather than promoted to production. Their weights stay outside Git and outside distributed APK/AAB artifacts.

The model must still pass Mozart's runtime adapter, token detokenizer and PatternProposalValidator gates before its musical output is considered usable.

## Current engineering consequence

No external checkpoint is promoted to the Mozart production manifest yet.

The present architecture therefore remains:

generation contract → Mozart 512-token vocabulary → future model-specific encoder → LiteRT backend → strict detokenizer → PatternProposalValidator.

The strongest reusable direction from the candidate survey is the architecture budget, not a pretrained weight file: approximately 40–50M causal Transformer parameters, with Mozart's own event vocabulary, conditioning representation, training-data provenance and export contract.

Before any pretrained checkpoint is integrated, the project must record its exact weight license, dataset provenance and checksum in the production model manifest.

## Next model gate

The next model-specific task is to choose between:

- independently training a Mozart-owned causal model in the 30–60M budget; or
- obtaining explicit commercial redistribution permission for a compatible external checkpoint.

Only after that choice should tensor names, shapes, quantization and LiteRT model wiring be frozen.
