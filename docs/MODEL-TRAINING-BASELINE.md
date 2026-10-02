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

The CI development checkpoint uses a separate synthetic conditioning fixture: control profiles are declared first and a deterministic renderer creates target MIDI from them. Each of density, energy, syncopation, swing and variation is exercised at low/high values while the other controls remain at a neutral baseline. This fixture exists specifically to prove that conditioning can be learned without deriving labels from the target sequence.

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

The CI conditioning fixture is a fit-capacity diagnostic rather than a model-selection
benchmark. Its validation split contains only one mixed control holdout, so using
that single validation loss for early stopping can select an early, under-trained
checkpoint even while the training objective is still learning the synthetic
control mapping. The CI greedy sequence gate therefore evaluates the final
requested training checkpoint (latest.pt), while the validation loss remains
reported for diagnostics.

The CI also records a teacher-forced diagnostic at the exact low/high target
divergence point for each control. This answers a different question from greedy
generation: whether the model assigns the correct target token high enough in
the learned context. The report is diagnostic-only for now; `--require-target-top1`
is available for a future stricter fit gate after the first reproducible results.

The greedy sequence gate validates generated output as a bounded grammar prefix.
It does not require EOS inside the fixed 32-token observation budget, because EOS
marks completion of a stream rather than validity of an unfinished autoregressive
window. A malformed continuation (for example a controller token emitted where
a note velocity is required) still fails immediately. Complete-stream validation
continues to require EOS in the standalone grammar contract.

Because this fixture intentionally contains only ten train records, the CI fit may
repeat those exact records within each epoch using `--repeat-train-records`. This
is deterministic repeated exposure, not data augmentation and not new musical
data; its purpose is to provide enough optimizer updates to test whether the
development architecture can actually fit the explicit conditioning signal.

The CI uses `--fit-diagnostic` for this tiny synthetic corpus. That mode keeps
the same model architecture and exported tensor shapes but disables dropout and
weight decay during this capacity test. The goal is to remove regularization as
a confound when asking the narrow question "can this architecture memorize and
respond to the explicit conditioning labels?" It is not the production training
recipe. The current CI budget is 12 epochs with 10 train records repeated 16
times, batch size 4: exactly 40 optimizer updates per epoch and 480 updates in
the final checkpoint. The checkpoint records this budget explicitly and CI
verifies it before ONNX export.

## Latest fit-diagnostic result

The reproducible 480-update fit diagnostic has now been executed successfully through
training and ONNX export. The final checkpoint reached train_loss=0.129450 after
12 epochs, while the one-record validation split reported validation_loss=22.605654.
The unconstrained greedy sequence gate still failed on MIDI grammar, so increasing
repeated exposure alone does not remove autoregressive collapse on this tiny corpus.

The same checkpoint produced matching PyTorch and ONNX greedy token sequences.
The separate teacher-forced diagnostic completed with 80 observed positions and
63 native target-top1 positions; only one of the five independently varied controls
had both low/high divergence targets at top-1. This separates two facts: conditioning
signals are reaching the model, but learned next-token control mapping is incomplete
and does not remain structurally reliable during free-running generation.

These results are evidence for the development baseline only. They do not justify
selecting this checkpoint for production. The next experiments should improve
autoregressive/grammar robustness and training diversity rather than merely increasing
the repetition factor or treating validation loss from the tiny holdout as a production
model-selection criterion.

The first follow-up experiment is a grammar-aware training-loss A/B test. With
`--grammar-constrained-loss`, each next-token cross-entropy term is normalized only
over tokens valid for the current frozen MIDI grammar state; the model architecture,
conditioning inputs, token vocabulary, optimizer budget and 480-update fit-diagnostic
budget remain unchanged. The resulting checkpoint is evaluated both with raw greedy
decoding and with the same runtime grammar-constrained decoder, plus the existing
teacher-forced diagnostic. This remains an experimental branch: the unconstrained
greedy stream can still collapse structurally, while grammar-constrained rollout can
remain valid even when a control does not change the discrete argmax sequence.

### Grammar-aware A/B result

The reproducible grammar-aware 480-update checkpoint reached train_loss=0.090398 and
validation_loss=19.501389. Grammar-constrained decoding produced structurally valid
bounded rollouts and PyTorch/ONNX greedy sequences matched for all five controls. Three
controls changed the discrete generated sequence; density and energy did not.

This exposes an important measurement distinction. Exact greedy-sequence divergence is
a brittle proxy for continuous conditioning because low/high controls can shift the
probability distribution without changing its argmax. The development evaluator now
records total-variation distance over the currently legal token distribution during
the shared rollout. The CI conditioning gate uses a maximum total-variation threshold
of 0.05 for every control in the grammar-constrained path, while unconstrained greedy
output remains diagnostic-only. This keeps structural validity and measurable control
influence as separate checks instead of treating raw autoregressive collapse as a
production-model signal.

## Training


    python tools/train_mozart_model.py \
        path/to/train.jsonl \
        --validation-jsonl path/to/validation.jsonl \
        --output-dir artifacts/mozart-model-v0 \
        --epochs 10 \
        --batch-size 4 \
        --seed 42

Training records must carry independently supplied `performance_controls`;
the example builder and window builder reject missing controls rather than
deriving them from the target event sequence.

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
