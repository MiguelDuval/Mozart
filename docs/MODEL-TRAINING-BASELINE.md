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

The teacher-forced diagnostic now separates raw-vocabulary target evidence from
the grammar-legal distribution used by the control-response metric. For every
observed target it reports legal-token target probability, the native-minus-
counterfactual probability lift, and the fraction of total variation attributable
to that target. It also records raw and legal-token target rank/top-1 separately.
The additional `--require-legal-target-top1` switch is available for a future
fit gate but is intentionally not enabled by the current CI gate. Teacher-forced
targets are rejected when the fixture or training record contains a token that is
not legal after its context, preventing malformed probe data from looking like
model evidence.

The diagnostic also verifies PyTorch/ONNX parity for the legal-token target
probability, legal-token rank/top-1, and the distribution TV measurement. A
control is additionally summarized as having a bidirectional target response
only when both its low-side and high-side divergence targets gain probability
under their corresponding native controls. The evaluator also measures the
probability mass of the target's legal MIDI token family. This provides a less
brittle semantic signal for controls where exact-token prediction is too narrow:
a control can increase the correct event family without making one exact token
the argmax. These metrics remain diagnostic-only; a large distribution shift,
family shift, or exact-token shift by itself is not proof that the model learned
the intended semantic mapping.

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

The ML workflow also publishes a compact `ml-semantic-ab-summary.json`
artifact containing the teacher-forced semantic metrics for both the regular and
grammar-aware checkpoints. This keeps A/B comparisons reproducible across CI runs
without turning the diagnostic into a production acceptance gate.

A second follow-up experiment is now available as a manual CI run:
the conditioning fixture can add deterministic target-MIDI context variants while
keeping the exact same performance-control labels. The diversity experiment adds 10 context variants to the first 10 control profiles,
producing 22 total records and 20 train records. Base and variant renderings have
unique record identities; each variant explicitly inherits the split assigned to its
base profile, yielding exactly 20 train / 1 validation / 1 test without duplicate
`source_id` values. With batch size 4 and `--repeat-train-records 8`, both the
matched-exposure baseline and the context-diverse fit receive exactly 480 optimizer
updates with seed 42. The matched-exposure baseline mirrors the exact ordering of
the 20 diverse train positions but substitutes the corresponding base target MIDI
for every variant position. This isolates target-context diversity from the otherwise
confounding change in example exposure. Architecture, conditioning schema, optimizer
family, learning rate and update budget stay fixed. This is an experimental diagnostic,
not a production training recipe. Teacher-forced and autoregressive evaluators in the manual experiment are
run independently, so a failed diagnostic does not prevent the other measurements or the
context-diverse fit from completing. Partial artifacts are preserved, and the summary records
teacher-forced plus grammar-constrained sequence evidence for the regular baseline,
matched-exposure baseline and context-diverse fit. The summary also computes
`diverse_minus_matched` deltas for fit loss, teacher-forced semantic response,
aggregate autoregressive response and per-control sequence/TVD response. The reporting
logic lives in `tools/summarize_mozart_conditioning_ab.py` with unit coverage in
`tests/test_summarize_mozart_conditioning_ab.py`; a diagnostic `FAIL` is recorded as
evidence but does not itself fail the manual CI job. The training-side A/B contract is
validated before either fit by `tools/validate_mozart_conditioning_ab.py`, with unit
coverage in `tests/test_validate_mozart_conditioning_ab.py`. That validator checks
unique source identities, exact 10/20/20 train cardinalities, control-label alignment,
base-target ordering, target identity of the matched baseline, and that each rendered
v1 context actually differs from its v0 base target. The validator also proves
that the diverse and matched probe definitions are identical apart from their
intentionally remapped synthetic record IDs, so A/B evaluation cannot silently
change prefixes or probe profiles. The original A/B probes carry explicit
`probe_context="canonical-base-records"` metadata and remain identical between the
matched-exposure and context-diverse fits. The cross-context follow-up adds a separate
v1 probe set built from an independently rendered musical prefix; that v1 definition is
shared by the matched and diverse models, so any difference is attributable to training
context diversity rather than a probe mismatch. Matched teacher-forced probes are
remapped to unique synthetic identities instead of reusing base fixture IDs. The validator also persists
`build/ml-context-diversity-input-contract.json`, covering both the diverse and
matched probe sets, including the shared fixture revision, so an experiment artifact
records the exact dataset/probe integrity checks that preceded training. The final
A/B summary also embeds this contract and refuses to report `PASS` when the contract
is missing or failed. This is intentional: a failed sequence
criterion is evidence worth inspecting, not a reason to discard the checkpoint or
other measurements.

### Context-diversity cross-context result

Run #227 on commit `86816b098a6dc441b7a5a3ec7f951cfde47b6417` completed the
independent-context v1 experiment end to end. The input contract passed, PyTorch/ONNX
evaluation completed for both models, and the final A/B summary reported no missing
required artifacts. Both fits used seed 42 and exactly 480 optimizer updates.

The matched-exposure fit reached train_loss=0.151701 and validation_loss=18.406799.
The context-diverse fit reached train_loss=0.451297 and validation_loss=13.099180,
a diverse-minus-matched validation-loss delta of -5.307619. The held-out validation
improvement therefore persisted in this independent run; the higher diverse train loss
is expected under the added context diversity and is not itself evidence of a failure.

The v1 teacher-forced diagnostic uses the same independent prefixes for both models and
observes 80 target positions. The matched model reached a target-probability directional
response rate of 0.4625, target-family directional response rate of 0.4375, mean target
probability delta of -0.001524, mean target-family probability delta of -0.002016,
mean distribution TV of 0.069946, and 1/5 controls with bidirectional target response.
The diverse model reached 0.5625, 0.4375, +0.018075, -0.002150, 0.066404, and 2/5
respectively. Thus context diversity improves the exact-target directional response
rate on the independent context (+0.100000) and the mean target probability delta
(+0.019600), while the target-family directional rate is unchanged and mean distribution
TV changes only slightly (-0.003542). This is evidence of better transfer to the new
context, not evidence that all five controls became robust.

The v1 grammar-constrained autoregressive diagnostic shows the remaining limitation.
The matched model changed the generated sequence for 0/5 controls, with mean
control-max-TV=0.102747 and a minimum of 0.048124; density and energy were below the
0.05 diagnostic threshold. The diverse model changed 3/5 controls, with mean
control-max-TV=0.164453 and a minimum of 0.044842; swing was below the threshold.
The generated streams remained grammar-constrained, and the PyTorch/ONNX control
distribution measurements were consistent.

The per-control diverse-minus-matched autoregressive changes are density +0.287944
(max-TV, sequence change +1), energy +0.222797 (+1), swing -0.113336 (0), syncopation
+0.044751 (+1), and variation -0.133629 (0). This confirms that the context-diversity
effect is control-specific rather than a uniform gain across the five performance
controls.

Methodologically, the result supports the conclusion that context diversity improves
generalization to an independent musical context and strengthens some teacher-forced
control evidence, but it does not by itself solve free-running autoregressive stability.
The next investigation should therefore remain focused on the gap between teacher-forced
conditioning and autoregressive control retention. No architecture or conditioning-gain
change is justified by this experiment alone.

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
