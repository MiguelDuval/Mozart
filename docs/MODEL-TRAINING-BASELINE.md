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

The CI development checkpoint uses a separate synthetic conditioning fixture: control profiles are declared first and a deterministic renderer creates target MIDI from them. Each of density, energy, syncopation, swing and variation is exercised at low/high values while the other controls remain at a neutral baseline. This fixture exists specifically to prove that conditioning can be learned without deriving labels from the target sequence. The current fixture revision is `mozart-conditioning-fixture-v2`.

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

## Probe methodology correction

The conditioning fixture was revised from v1 to v2 to remove an avoidable confound in the low/high control probes. The paired 0.1 and 0.9 profiles for each independently varied control now share the same deterministic renderer seed, and their stored conditioning seeds are aligned as well. Because seed is not a model input, this keeps the paired target difference attributable to the declared control rather than to an unobserved target-generation seed. Mixed control profiles retain distinct seeds. Bumping the fixture revision intentionally invalidates the earlier v1 measurements as direct evidence for the current probe definition; the CI experiment must be rerun before new v2 numerical claims are made.

## Latest fit-diagnostic result

The reproducible 480-update fit diagnostic was executed successfully through
training and ONNX export for fixture revision v1. The final checkpoint reached train_loss=0.129450 after
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
context-variant file (`control-probe-*-v1.mid`) actually differs from its v0 base target. The validator also proves
that the diverse and matched probe definitions are identical apart from their
intentionally remapped synthetic record IDs, so A/B evaluation cannot silently
change prefixes or probe profiles. Sequence probes carry explicit
`probe_context="canonical-base-records"` metadata: diversity variants expand the
training contexts, while teacher-forced/autoregressive probes remain anchored to the
canonical base contexts so both A/B fits use the same probe definition. Matched
teacher-forced probes are remapped to unique synthetic identities instead of reusing
base fixture IDs. The validator also persists
`build/ml-context-diversity-input-contract.json`, covering both the diverse and
matched probe sets, including the shared fixture revision, so an experiment artifact
records the exact dataset/probe integrity checks that preceded training. The final
A/B summary also embeds this contract and refuses to report `PASS` when the contract
is missing or failed. This is intentional: a failed sequence
criterion is evidence worth inspecting, not a reason to discard the checkpoint or
other measurements.

The context-diversity A/B experiment is available as a manual CI run via workflow_dispatch. For environments where workflow dispatch cannot be invoked through the available automation interface, an explicit push commit containing `[run-diversity-experiment]` is also supported on non-main branches; ordinary pushes remain unchanged. The first follow-up experiment is a grammar-aware training-loss A/B test. With
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

## Corrected v2 fit-diagnostic result

The corrected mozart-conditioning-fixture-v2 experiment was executed successfully in
GitHub Actions run 37147326682 at commit c30ef15017a714cb8bbb6d7dcda304d2bf485596.
The fixture's low/high probe pairs now share both renderer seed and stored conditioning
seed, so these measurements remove the v1 target-generation seed confound.

The regular development checkpoint completed the full 480-update budget at epoch 12 with
train_loss=0.130827 and validation_loss=20.581295. The final checkpoint still fails the
unconstrained autoregressive grammar probe: all five control probes can be structurally
invalid during free-running greedy decoding. This remains diagnostic evidence only and
does not make the CI job fail.

Teacher-forced evaluation on the corrected fixture observed 80 target positions. The
regular checkpoint had 55 raw-vocabulary target-top1 positions and 59 grammar-legal
target-top1 positions. All five independently varied controls showed bidirectional target
probability response, while only one control had both low/high divergence targets at
raw target-top1. The target-probability directional response rate was 0.5875, the target
family directional response rate was 0.425, the mean native-minus-counterfactual target
probability delta was 0.0363614900, and mean legal-distribution total variation was
0.0728490066. The mean target-family probability delta was -0.0062887546, reinforcing
that exact-token movement is a more sensitive signal here than coarse family mass.

The grammar-aware checkpoint completed the same 480-update budget at epoch 12 with
train_loss=0.144798 and validation_loss=21.311838. Its grammar-constrained autoregressive
probe passed: all five control paths remained valid for the bounded 32-token rollout,
and PyTorch/ONNX generated sequences matched. The constrained distribution-response
criterion also passed with the configured minimum total-variation threshold of 0.05.
The corresponding teacher-forced report observed 80 positions, with 2 raw target-top1
positions and 68 grammar-legal target-top1 positions; all five controls again showed
bidirectional target probability response. Target-probability directional response was
0.575, target-family directional response was 0.4, mean target-probability lift was
0.0578539339, and mean legal-distribution total variation was 0.0811333709. Only one
control reached both legal targets at top-1, and none reached both raw targets at top-1.

These v2 results materially strengthen the methodological case that the conditioning
signals influence the model, but they do not establish robust production-quality
conditioning. In particular, the tiny synthetic corpus remains easy to overfit,
validation loss is unstable, and grammar-constrained validity is being measured over a
fixed unfinished window rather than a complete generated musical phrase. The next
scientific step is therefore the manual context-diversity A/B experiment: compare the
matched-exposure and context-diverse fits under the already frozen 480-update budget,
using the corrected v2 fixture and identical canonical probes. Do not compare its
numbers as if they were production-model acceptance metrics.
## Context-diversity A/B result (v2)

The explicit context-diversity experiment completed successfully in GitHub Actions run 37157412404 on the corrected v2 fixture. The input contract passed: 20 diverse train records, a 20-position matched-exposure baseline, unique source identities, target-identical matched contexts, and identical canonical five-control probes.

The matched-exposure baseline used the same 480 optimizer updates as the diverse fit (12 epochs, repeat factor 8, seed 42). It reproduced the regular baseline checkpoint exactly at train_loss=0.1308269174 and validation_loss=20.5812950134. Its grammar-constrained canonical probe changed the generated sequence for 3 of 5 controls, with mean per-control maximum TV=0.4695027829 and maximum=0.8021092739.

The context-diverse fit also used exactly 480 optimizer updates and reached train_loss=0.4412642833 and validation_loss=13.0907974243. Its train loss is intentionally higher because it must fit distinct target contexts instead of repeated target-identical exposures. Despite that, validation loss improved by 7.4904975891 and grammar-constrained canonical probes changed the generated sequence for all 5 controls. Mean per-control maximum TV was 0.2263220105 and maximum=0.4484889095.

Teacher-forced conditioning did not improve uniformly. The diverse fit increased the target-probability directional response rate from 0.5875 to 0.6625 (+0.075) and the family directional response rate from 0.425 to 0.4375 (+0.0125), but reduced mean target-probability lift from 0.0363614900 to 0.0175043867 and mean legal-distribution TV from 0.0728490066 to 0.0615715698. In the grammar-constrained sequence diagnostic, the number of controls with sequence changes increased from 3 to 5, while aggregate maximum-TV response decreased.

The correct interpretation is therefore that target-context diversity changes the model's generalization/conditioning trade-off rather than simply making conditioning stronger. The lower held-out loss and broader discrete sequence response are encouraging, but the validation split still contains only one mixed control holdout and the experiment uses one random seed. These results are not sufficient to select a production checkpoint.

The next scientific gate should be replication of the matched-vs-diverse comparison across multiple deterministic seeds, preserving the same v2 split, canonical probes, architecture and 480-update budget. The purpose is to estimate whether the validation-loss improvement and broader autoregressive response survive training stochasticity before changing the model architecture or production ABI.
## Multi-seed context-diversity replication result (v2)

Three deterministic replications of the matched-exposure versus context-diverse experiment completed successfully on corrected fixture v2 with seeds 7, 42 and 123. Each seed preserved the same 480-update budget, architecture, learning rate and canonical five-control probes. The research jobs themselves all passed; the original aggregate step failed only because three identically named seed summary files were flattened into one path, which is now fixed in the replication workflow.

Across seeds, context diversity consistently improved the single held-out validation loss: the diverse-minus-matched delta averaged -10.182218 with sample standard deviation 1.883987. Train loss increased by about 0.272 on each replication because the diverse fit must model distinct target contexts rather than target-identical repeated exposure.

Teacher-forced target-probability directional response decreased by an average 0.054167 (sample SD 0.014434), while target-family directional response decreased by 0.029167 on average (sample SD 0.064145). Mean target-probability lift changed by -0.008125 on average (sample SD 0.014132), and mean legal-distribution TV changed by -0.004938 on average (sample SD 0.021271). These effects are much less stable than the validation-loss improvement and include mixed signs across seeds for family response, target lift and teacher-forced TV.

Grammar-constrained autoregressive response was mixed in discrete sequence count but consistently lower in aggregate TV. The diverse-minus-matched delta for controls with sequence changes averaged +0.333 controls (sample SD 1.528), while mean per-control maximum TV decreased by 0.157608 (sample SD 0.137609). The strongest per-control TV reduction was swing (mean max-TV delta -0.383486); density was the only control with a slightly positive mean max-TV delta (+0.017796).

The three-seed replication therefore supports a narrower conclusion than the single-seed result: context diversity is a robust generalization intervention for this tiny synthetic task, but it is not a uniformly stronger conditioning intervention. In particular, validation loss improved in all three seeds, while exact target-probability responsiveness generally weakened. Because the validation set still contains only one mixed holdout example, these results remain development evidence rather than a production model-selection rule.

The next experiment should separate generalization from conditioning strength more cleanly by expanding the held-out control contexts and repeating the A/B comparison without changing the 480-update budget. Do not freeze the production model ABI or select a production checkpoint from this result alone.
## Corrected 2x2 diversity factorial result

A corrected four-arm causal decomposition completed successfully in GitHub Actions
run 37211020382 on fixture revision `mozart-conditioning-fixture-v2`, with seeds
7/42/123 and exactly 480 optimizer updates per fit.

The fit-level mean validation-loss deltas versus matched exposure were:
- target-only: -6.810434 ± 0.473392;
- conditioning-only: -2.773605 ± 0.252297;
- joint: -7.501675 ± 0.854254;
- target × conditioning interaction: +2.082363 ± 1.397880.

Thus both target diversity and conditioning coverage improve validation loss on this
fixture, but their effects are non-additive under the fixed training budget.

On the four completely unseen validation contexts, the mean target-probability
directional-response deltas were +0.019792 for target-only, +0.003125 for
conditioning-only, and +0.025000 for the joint arm. Conditioning-only therefore
does not reproduce the earlier directional-alignment effect. Its more stable signal
is reduced distribution TV: -0.033985 mean teacher-forced TV and -0.170297 mean
per-control maximum autoregressive TV.

The target-only and joint arms retain positive held-out target-probability directional
response, while target-family response remains noisy. The current safe interpretation
is that conditioning coverage has an independent generalization effect but is not
sufficient to explain the held-out directional-response improvement. Reduced TV should
be interpreted as reduced distribution shift/selectivity, not automatically as stronger
conditioning.

The first factorial workflow attempt (37207001692) failed only because the aggregate
runner lacked repository checkout. The clean rerun 37211020382 completed all seed and
aggregate jobs with PASS and produced the factorial summary artifact.

This remains synthetic development evidence. It does not select a production checkpoint,
freeze the tensor ABI, or justify LiteRT integration.

The next diagnostic is a five-level conditioning dose-response sweep at
0.1/0.3/0.5/0.7/0.9, comparing matched exposure with the target/context-diverse fit.
The new evaluator records the signed high-target-versus-low-target probability curve,
slope around neutral, monotonic consistency, integrated absolute response, legal-family
response, and TV relative to neutral with PyTorch/ONNX parity checking.

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
