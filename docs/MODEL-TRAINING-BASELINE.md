# Mozart model training baseline

## Status

This is a development-only architecture baseline, not a production model and not
a frozen deployment ABI.

The first trainable target is mozart-symbolic-transformer-v0:

- 512 Mozart event tokens;
- 1,024-token maximum context;
- 576-dimensional hidden state;
- 8 attention heads;
- 8 causal Transformer encoder blocks;
- 2,304-dimensional feed-forward blocks;
- GELU activation;
- pre-normalization;
- tied token embedding/output projection;
- exactly 32,817,024 parameters for the configured architecture.

The architecture uses the five conditioning axes already emitted by the current
training corpus:

- style;
- substyle;
- mood;
- rhythm;
- role.

Each conditioning axis is represented by a learned embedding and added to the
token/position representation before the causal Transformer.

The baseline deliberately does not claim that key/scale, continuous macro controls,
LiteRT tensor names or production sampling policy are frozen. Those remain future
model-dependent decisions. Key/scale and range constraints remain enforced by
Mozart's post-generation musical validation.

## Training input

The existing JSONL training records from tools/midi_to_training_example.py are
consumed directly. The model learns next-token prediction.

PAD positions are ignored by the loss. Conditioning slugs are validated before
each record enters the dataset.

## Determinism

The trainer accepts an explicit seed and applies it to Python and PyTorch. CUDA
determinism settings are enabled when CUDA is available. The training DataLoader
uses a seeded generator.

Training checkpoints are written only to the requested output directory. Model
weights are ignored by Git and must not be committed.

## Training command

Use a dedicated PyTorch environment outside the Android build:

    python tools/train_mozart_model.py \
        path/to/train.jsonl \
        --validation-jsonl path/to/validation.jsonl \
        --output-dir artifacts/mozart-model-v0 \
        --epochs 10 \
        --batch-size 4 \
        --seed 42

The script prefers CUDA when available unless --device cpu is selected explicitly.

## Deployment gate

A trained checkpoint remains experimental until all of the following are completed:

1. held-out musical validity and conditioning evaluation;
2. export of the actual trained checkpoint;
3. inspection of resulting ONNX/LiteRT tensors;
4. versioned model manifest containing the exact tensor contract and quantization;
5. TokenInferenceBackend integration;
6. Android latency and memory benchmark;
7. model/data licensing review.

No model weights are included in this repository.
