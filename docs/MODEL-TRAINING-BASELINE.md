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
- exactly 32,820,480 parameters for the configured architecture.

The architecture uses the five categorical conditioning axes already emitted by
the current training corpus: style, substyle, mood, rhythm and role. It also
includes a small continuous performance-control projection for density, energy,
syncopation, swing and variation. Training records receive these controls from
independent intent/context labels rather than from the target event sequence,
while live performance state uses the same normalized fields at runtime. The
retrospective `derive_performance_controls()` helper is reserved for QA metrics
and is not used to construct model conditioning. This remains a development
baseline; the production tensor ABI is not frozen.

The baseline deliberately does not claim that key/scale, continuous macro controls,
LiteRT tensor names or production sampling policy are frozen. Those remain future
model-dependent decisions. Key/scale and range constraints remain enforced by
Mozart's post-generation musical validation.

## Training input

The existing JSONL training records from tools/midi_to_training_example.py are
consumed directly. The model learns next-token prediction and masks padded
positions from the loss. Conditioning slugs are validated before training.

## Determinism

The trainer accepts an explicit seed and applies it to Python and PyTorch. CUDA
determinism settings are enabled when available, and the shuffled training loader
uses a seeded generator.

Checkpoints are written only to the requested output directory. Model artifacts
are ignored by Git and must not be committed.

## Training

Use a dedicated PyTorch environment outside the Android build:

    python tools/train_mozart_model.py \
        path/to/train.jsonl \
        --validation-jsonl path/to/validation.jsonl \
        --output-dir artifacts/mozart-model-v0 \
        --epochs 10 \
        --batch-size 4 \
        --seed 42

## ONNX export

An experimental exporter can turn a trained checkpoint into a concrete ONNX graph:

    python tools/export_mozart_onnx.py \
        artifacts/mozart-model-v0/best.pt \
        artifacts/mozart-model-v0/model.onnx

The exporter names the baseline graph inputs:

- input_ids;
- style_id;
- substyle_id;
- mood_id;
- rhythm_id;
- role_id.

The output is logits with the final 512-token Mozart vocabulary dimension.

The exporter uses the actual model graph, so the resulting tensor names and
ranks can be inspected from the produced ONNX artifact. They are experimental
facts of this checkpoint/configuration, not a production ABI.

## Deployment gate

A trained checkpoint remains experimental until held-out musical evaluation,
actual export inspection, a versioned model manifest, backend integration, Android
latency/memory benchmarking, and model/data licensing review are complete.

No model weights or ONNX artifacts are included in this repository.
