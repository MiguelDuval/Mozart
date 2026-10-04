# Context-diversity holdout replication (2026-10-04)

## Purpose

This experiment tests whether the context-diversity generalization effect survives
when validation is expanded beyond the single mixed holdout used by the earlier
v2 diagnostic.

The training architecture, optimizer family, learning rate, fit-diagnostic mode,
canonical conditioning probes and 480-optimizer-update budget remain unchanged.
Only the synthetic fixture's base split is expanded from 10 train / 1 validation /
1 test to 10 train / 4 validation / 2 test base contexts.

For the diversity arm, 10 additional target-context variants are added to the
10 train base profiles. The resulting corpus therefore contains 26 records:
20 train, 4 validation and 2 test. The matched arm has 20 train positions with
the original target MIDI repeated at each variant position. Validation and test
records are shared between the two arms.

The canonical autoregressive probes remain anchored to the five paired train
control profiles. This intentionally separates held-out generalization loss from
the existing conditioning-response diagnostic.

## Reproducibility

- Branch: `feature/link-clock`
- Experiment commit: `e6932fbb5ecda106d06df8bd5bf5d850f1253ab0`
- Research workflow run: `37162482566`
- Fixture revision: `mozart-conditioning-fixture-v2`
- Seeds: 7, 42, 123
- Optimizer updates per fit: 480
- Batch size: 4
- Repeat-train-records: 8
- Learning rate: 3e-4
- Device: CPU
- Input contract: PASS for all three seeds
- Seed jobs: PASS for all three seeds
- Aggregate job: PASS

## Aggregate result

All three seeds improved held-out validation loss:

| Metric | Mean diverse - matched | Sample SD | Per-seed |
| --- | ---: | ---: | --- |
| Validation loss delta | -6.565419 | 0.872208 | seed 7: -6.834727; seed 42: -5.590318; seed 123: -7.271212 |
| Target-probability directional response-rate delta | +0.008333 | 0.059073 | -0.012500; +0.075000; -0.037500 |
| Target-family directional response-rate delta | +0.029167 | 0.040182 | +0.075000; +0.012500; 0.000000 |
| Mean target-probability delta delta | -0.016445 | 0.004616 | -0.019356; -0.018857; -0.011123 |
| Mean teacher-forced distribution TV delta | -0.012436 | 0.015231 | -0.028213; -0.011277; +0.002183 |
| Controls with sequence-change delta | +0.666667 | 1.527525 | +1; +2; -1 |
| Mean per-control maximum TV delta | -0.182446 | 0.082080 | -0.215092; -0.243181; -0.089067 |

The train-loss delta remained positive in every seed because the diverse arm must
fit distinct target contexts instead of repeatedly exposing identical target MIDI.
This is expected by design and is not evidence against the intervention.

## Interpretation

The expanded holdout materially strengthens the generalization result. Validation
loss improved in every seed, with substantially smaller between-seed variation than
the earlier single-holdout replication.

The conditioning-response picture is still mixed:

- Exact target-probability directional response is approximately flat on average
  and changes sign across seeds.
- Target-family directional response is non-negative in all three seeds, but the
  magnitude is small.
- Mean target probability lift decreases in all three seeds.
- Teacher-forced distribution TV decreases in two seeds and increases slightly in
  one.
- Grammar-constrained autoregressive response shows mixed discrete sequence-count
  changes, while mean per-control maximum TV decreases in all three seeds.

The defensible conclusion is therefore narrower than "diversity strengthens
conditioning": context diversity is a reproducible generalization intervention on
this synthetic task, while its effect on the strength of explicit control
conditioning remains unresolved and may involve a trade-off between target-context
memorization and control responsiveness.

These results are development evidence only. They do not justify selecting a
production checkpoint, freezing the model ABI, or treating this tiny synthetic
fixture as a substitute for held-out musical data.

## Audit correction

An earlier repository note described a multi-seed context-diversity replication
with a single validation example. The associated push-triggered research run on
commit `e6095e4d8cb9093393b67fb84739107264e1c628` was actually skipped, and its
artifact naming was incomplete. That historical note must not be treated as a
verified multi-seed result. The verified multi-seed evidence in this document is
the completed run `37162482566` at commit `e6932fbb5ecda106d06df8bd5bf5d850f1253ab0`.

## Held-out conditioning gate

The next gate was executed as planned on four validation contexts that are excluded
from training. Each unseen context has five controls, each control is evaluated at
low/high values, producing 20 paired control probes and 40 evaluation-only records.
The probe records are generated from the shared validation split and are not added
to either training arm.

- Implementation/fix commits: `6bc212ae8309eea8946d5098c3199ac97847b5ab6`,
  `c41452f79ce2738e98ba858d5f67b31cb8dfea07`,
  `00ae4f09b899322ec7b390232e5d2fa8d42f7ac6`
- Trigger commit: `e64837a05203d9659431757336f57ef96caad988`
- Research workflow run: `37184160533`
- Seeds: 7, 42, 123
- Optimizer updates per fit: 480
- Held-out contexts: 4
- Held-out control probes: 20 pairs / 40 records
- Seed jobs: PASS for all three seeds
- Held-out teacher-forced scoring: PASS for all three seeds
- Held-out grammar-constrained sequence scoring: PASS for all three seeds
- Cross-seed aggregate: PASS
- Android build on the same branch tip: PASS

### Held-out result

All values below are diverse minus matched. The per-seed values are computed over
the four held-out validation contexts; the aggregate mean/SD is across the three
independent seeds.

| Metric | Seed 7 | Seed 42 | Seed 123 | Mean ± sample SD |
| --- | ---: | ---: | ---: | ---: |
| Target-probability directional response-rate delta | +0.043750 | +0.018750 | +0.028125 | +0.030208 ± 0.012630 |
| Target-family directional response-rate delta | +0.028125 | +0.006250 | +0.009375 | +0.014583 ± 0.011831 |
| Mean target-probability lift delta | -0.001061 | +0.009200 | +0.007690 | +0.005276 ± 0.005540 |
| Mean teacher-forced distribution TV delta | -0.012073 | -0.013390 | -0.002130 | -0.009198 ± 0.006156 |
| Controls with sequence-change delta | +1.000000 | +1.250000 | +1.000000 | +1.083333 ± 0.144338 |
| Mean per-control max TV delta | -0.088282 | -0.116584 | -0.138054 | -0.114307 ± 0.024964 |

The strongest reproducible signal is directional alignment on unseen contexts:
all three seeds improve the target-probability directional response rate, and all
three also improve target-family directional response rate. The autoregressive
suite likewise shows more controls producing a sequence change in every seed.

At the same time, the magnitude story is not a simple "stronger conditioning"
result. Raw mean target-probability lift is positive in two seeds and negative in
one, while teacher-forced distribution TV and mean per-control autoregressive TV
both decrease consistently. That pattern is compatible with a more selective or
regularized control response rather than uniformly larger sensitivity.

Because this is still a tiny synthetic fixture, the defensible conclusion is:
context diversity now has reproducible evidence of improving conditional-response
alignment on unseen validation contexts, while its effect on response magnitude
and overall conditioning strength remains unresolved. This does not justify
calling diversity a production conditioning solution, selecting a production
checkpoint, or freezing the model ABI.

The held-out evaluator also keeps grammar validity and PyTorch/ONNX consistency as
hard gates. All three seeds passed those gates; this is an infrastructure and
model-consistency result, not evidence that the synthetic sequences are
production-quality musical output.

## Third-gate implementation: target-fixed conditioning-context control

The third arm is implemented as a target-fixed causal control rather than a new
model variant. Starting from the same 10 canonical train records used by the
matched-exposure arm, it creates 20 train positions: one unchanged copy plus one
copy whose model-visible categorical conditioning fields are replaced by a
deterministic diverse context profile.

The invariant is strict:

- target MIDI bytes, token streams, target SHA-256 values and performance controls
  are identical to the matched arm at every train position;
- conditioning seed is unchanged;
- only the five categorical conditioning fields actually consumed by the
  Transformer (style, substyle, mood, rhythm, role) vary on the ten
  context-diverse positions;
- the same four validation contexts, five controls, three seeds, optimizer,
  learning rate, batch size, repeat factor and 480-update budget are preserved.

The experiment therefore tests a narrower causal question than the prior
target-diversity intervention: whether broader coverage of the conditioning
input space alone can change held-out behavior when target-sequence exposure is
held fixed. Because some varied contexts are intentionally paired with the same
target sequence, this arm is a context-coverage/label-consistency diagnostic,
not a claim of realistic data augmentation.

Implementation commits on feature/link-clock:
588fb90accdc9a303988313aca42aebf473e2e87,
6f5c883b3d807515f275311aa1f46f32f3042014,
ace01a48b015119d2743a53017af3b1fbc4b63fc,
47dea816a45d628c99c97302daac99d9bd721aa3.

Run 37186038694 was an intermediate implementation run. The final three-seed
verification after the inline-Python repair is 37188595898 at commit
256cc82b04cd049653b8e636401bfbbc1bb9cc93; all seed jobs and the aggregate job
completed successfully.

## Third-gate results: target-fixed conditioning-context control

The final run compares three development arms against the same matched-exposure
baseline:

1. **Matched**: repeated target MIDI with canonical conditioning.
2. **Target/context-diverse**: the existing diversity intervention, where the
   added training positions change target/context together.
3. **Conditioning-context-diverse, target-fixed**: the new causal control, where
   the target tokens, target SHA-256, source path, performance controls and
   conditioning seed are fixed while only the five model-visible categorical
   fields (`style`, `substyle`, `mood`, `rhythm`, `role`) vary.

The target-fixed control contract passed for all three seeds. Each seed used 20
training records, 10 deterministic conditioning profiles, the same four held-out
contexts, five controls, three seeds, and exactly 480 optimizer updates with
batch size 4, repeat factor 8 and learning rate 3e-4.

### Overall fit result

All three seeds improved validation loss under the conditioning-only intervention,
but the gain was smaller than in the target/context-diverse arm:

| Arm vs matched | Mean validation-loss delta | Sample SD | Per-seed |
| --- | ---: | ---: | --- |
| Target/context-diverse | -6.786039 | 1.172136 | -6.834727; -5.590318; -7.933073 |
| Conditioning-context-diverse, target-fixed | -2.663849 | 1.765683 | -3.002584; -0.753338; -4.235624 |

This is evidence that, on this synthetic fixture, changing model-visible
conditioning coverage alone can improve held-out loss. It is **not** a valid
additive decomposition of the full diversity gain: the target/context-diverse
arm changes target exposure and conditioning together, so interaction remains
possible.

### Held-out conditioning result

All values are diverse-arm minus matched-arm deltas over the four completely
unseen validation contexts. The important causal comparison is between the two
diverse arms:

| Metric | Target/context-diverse mean ± SD | Conditioning-only mean ± SD |
| --- | ---: | ---: |
| Target-probability directional response-rate delta | +0.020833 ± 0.021949 | -0.004167 ± 0.030831 |
| Target-family directional response-rate delta | -0.004167 ± 0.038569 | -0.031250 ± 0.026700 |
| Mean target-probability lift delta | +0.005990 ± 0.006113 | +0.001754 ± 0.003024 |
| Mean teacher-forced distribution TV delta | -0.000745 ± 0.020771 | -0.031505 ± 0.016379 |
| Controls with sequence-change delta | +1.500 ± 0.661 | -0.417 ± 2.126 |
| Mean per-control max autoregressive TV delta | -0.104390 ± 0.014551 | -0.147429 ± 0.052570 |

The conditioning-only arm therefore does **not** reproduce the previously
observed held-out directional-alignment effect. Target-probability directional
response is positive for seed 7 but negative for seeds 42 and 123. Target-family
directional response decreases for all three seeds. The magnitude metrics also
move toward smaller distribution response: held-out teacher-forced TV decreases
in all three seeds, and mean per-control autoregressive max TV decreases in all
three seeds.

The strongest safe interpretation is consequently two-part:

- conditioning-context diversity alone is sufficient to produce a reproducible
  validation-loss improvement on this fixture;
- it is **not** sufficient to reproduce the earlier held-out directional-response
  improvement, and the observed TV reduction is compatible with a more selective
  or regularized response rather than uniformly stronger conditioning.

The target/context-diverse arm still has the stronger validation improvement and
better held-out target-probability directional response on average. We should not
claim that target diversity is the sole cause either, because that arm also changes
conditioning. The current three-arm evidence establishes that conditioning coverage
has an independent effect on generalization, while leaving target-vs-conditioning
main effects and their interaction unresolved.

### Gate integrity

The final workflow 37188595898 passed all three seed jobs and the aggregate job.
For every seed, the target-fixed contract reported PASS, the exact 480-update fit
contract passed, grammar-constrained validation remained valid, and PyTorch/ONNX
consistency checks passed. The separate strict conditioning sequence diagnostic
artifacts also remained PASS for seeds 7, 42 and 123 with no failures and the
0.05 response threshold retained. Low-TV observations in the non-strict control
summary were therefore reported as diagnostics rather than hidden or converted
into false failures.

No model architecture, tensor ABI, Android integration or production checkpoint
was changed by this gate. The artifacts are synthetic development evidence only.

## Next scientific gate: complete the 2x2 causal decomposition

The third gate rules in conditioning-only as a sufficient explanation for the
held-out alignment effect, but the existing target/context-diverse arm still mixes
target-sequence diversity with conditioning diversity. The next minimal causal
step is therefore a factorial control:

- **Matched:** target fixed + conditioning fixed (already present).
- **Target-only:** target diverse + canonical conditioning fixed (new arm).
- **Conditioning-only:** target fixed + conditioning diverse (already present).
- **Both:** target diverse + conditioning diverse (already present).

Use the same four held-out contexts, five controls, 20 train positions, three seeds,
optimizer settings and 480-update budget. The target-only arm should reuse the
existing diverse target sequences while forcing all five model-visible conditioning
fields back to the canonical fixture context. This will allow direct estimation of
the target main effect and the target×conditioning interaction without changing the
model, tensor ABI or Android path.

## Corrected 2x2 factorial gate — seed-level result

The corrected branch implements the planned four-arm causal decomposition without changing
the model architecture, tensor ABI, Android integration or production checkpoint.

The four arms are:
1. **Matched** — target fixed + conditioning fixed.
2. **Target-only** — target diverse + canonical conditioning, constructed from the joint
   exposure and forced back to canonical conditioning.
3. **Conditioning-only** — target fixed + conditioning diverse.
4. **Both / joint** — target diverse + conditioning diverse.

All arms retain 20 train positions, four completely unseen validation contexts, the same
five control probes, seeds 7/42/123, batch size 4, repeat factor 8, learning rate 3e-4
and exactly 480 optimizer updates.

The corrected joint builder enforces unchanged target tokens, target SHA-256 values,
source paths, performance controls and conditioning seeds, while varying only the five
model-visible categorical conditioning fields on the ten context-diverse variants. The
target-only builder refuses canonical-conditioning input, preventing the historical
no-op control from being silently accepted.

Implementation commits on `feature/link-clock`:
`f7f92991`, `87e682b4`, `e9402266`, `4fcd79af`, `750cbf2a`,
`104027ed`, `92df0732`, `cc442c88`, `2986b85d`, `4715ff29`,
`c706e6a6`.

### Seed-level factorial results

Workflow `37207001692` produced three successful seed jobs (7, 42, 123). The aggregate
job in that run failed only because the aggregate runner did not check out repository
sources before invoking `tools/summarize_mozart_factorial.py`; therefore the numerical
values below are independently reconstructed from the three uploaded seed artifacts,
not from a successful aggregate job.

All values are arm minus matched, with the interaction computed per seed as
`joint - target-only - conditioning-only`.

| Metric | Target-only | Conditioning-only | Joint | Interaction |
| --- | ---: | ---: | ---: | ---: |
| Validation-loss delta | **-6.7860 ± 1.1721** | **-2.6638 ± 1.7657** | **-6.8373 ± 1.7809** | **+2.6126 ± 1.5536** |
| Target-prob directional response | 0.0000 ± 0.0696 | +0.0125 ± 0.0217 | -0.0292 ± 0.0402 | -0.0417 ± 0.1301 |
| Target-family directional response | +0.0250 ± 0.0451 | +0.0333 ± 0.0577 | +0.0542 ± 0.0832 | -0.0042 ± 0.0971 |
| Mean target-probability lift | -0.0113 ± 0.0135 | -0.0050 ± 0.0175 | -0.0256 ± 0.0083 | -0.0094 ± 0.0230 |
| Mean teacher-forced TV | -0.0190 ± 0.0086 | **-0.0343 ± 0.0160** | **-0.0526 ± 0.0096** | +0.0008 ± 0.0124 |
| Controls with sequence change | +1.667 ± 0.577 | +0.333 ± 1.528 | -0.333 ± 1.155 | -2.333 ± 3.055 |
| Mean per-control max TV | **-0.2076 ± 0.0399** | **-0.1850 ± 0.0832** | **-0.2992 ± 0.0584** | +0.0934 ± 0.0697 |

The key fit result is clear on this fixture: both target diversity and conditioning-only
coverage improve held-out validation loss, with target diversity producing the larger
mean improvement. The positive interaction in validation loss means the joint effect
is less negative than the sum of the two main effects; the two interventions are therefore
not additive under this training budget.

The conditioning-response result is different. Conditioning-only does **not** reproduce
the earlier held-out directional-alignment effect: its target-probability directional
response is near zero on average, and target-family directional response is negative on
the four-context held-out comparison below. Its strongest consistent change is a
reduction in distribution TV. Therefore TV reduction must not be translated into
"stronger conditioning".

### Held-out four-context results

The four completely unseen validation contexts give the following arm differences:

| Metric | Target-only | Conditioning-only | Joint | Interaction |
| --- | ---: | ---: | ---: | ---: |
| Target-prob directional response | **+0.0208 ± 0.0219** | -0.0042 ± 0.0308 | **+0.0146 ± 0.0018** | -0.0021 ± 0.0498 |
| Target-family directional response | -0.0042 ± 0.0386 | **-0.0313 ± 0.0267** | -0.0240 ± 0.0266 | +0.0115 ± 0.0403 |
| Mean target-probability lift | +0.0060 ± 0.0061 | +0.0018 ± 0.0030 | +0.0039 ± 0.0035 | -0.0039 ± 0.0055 |
| Mean teacher-forced TV | -0.0007 ± 0.0208 | **-0.0315 ± 0.0164** | **-0.0333 ± 0.0138** | -0.0010 ± 0.0235 |
| Controls with sequence change | +1.500 ± 0.661 | -0.417 ± 2.126 | -1.417 ± 1.181 | -2.500 ± 2.179 |
| Mean per-control max TV | -0.1044 ± 0.0146 | **-0.1474 ± 0.0526** | **-0.1891 ± 0.0146** | +0.0627 ± 0.0435 |

These are cross-seed means of the already aggregated four-context measurements; the
`±` values are sample SD across seeds.

The strongest safe conclusion is now more specific than the earlier three-arm result:
**conditioning coverage has an independent generalization effect, but it is not sufficient
to explain the held-out directional-response improvement.** The positive held-out
target-probability directional signal is concentrated in the target-diverse arm and
remains present in the joint arm, while conditioning-only reduces distribution shift
without reliably increasing directional response.

The interaction terms are exploratory because there are only three training seeds and the
fixture is deliberately tiny. They should not be read as statistically powered causal
effect estimates.

### CI verification status

The clean-checkout rerun triggered by commit
`e6a81522e2915695080b3318fe887e6b2559f72a` completed successfully as workflow
`37211020382`.

- seed 7: PASS
- seed 42: PASS
- seed 123: PASS
- aggregate factorial: PASS

The published `mozart-ml-diversity-factorial-summary` artifact was produced successfully.
Its values match the seed-level reconstruction recorded above. The earlier
`37207001692` failure is therefore treated strictly as an aggregate checkout defect,
not as a failed scientific fit.

### Scientific next gate

The next minimal experiment should resolve the remaining ambiguity around conditioning
*magnitude* rather than changing the model. Keep the same checkpoints, contexts and frozen
ABI, and replace the single 0.1↔0.9 measurement with a symmetric dose-response sweep
(e.g. 0.1, 0.3, 0.5, 0.7, 0.9) for each performance control.

Measure:
- monotonic directional consistency across levels;
- slope around the neutral 0.5 point;
- integrated absolute probability response;
- change in legal-family probability;
- legal-distribution TV relative to 0.5.

This distinguishes "more selective response at similar magnitude" from genuine loss/gain of
conditioning sensitivity without changing the training architecture.


## Conditioning dose-response gate — implementation

The next diagnostic is implemented on `feature/link-clock` as a separate workflow,
`.github/workflows/ml-conditioning-dose-response.yml`.

It preserves the corrected v2 fixture, 20-position matched exposure, 20-position
target/context-diverse training arm, seeds 7/42/123, batch size 4, repeat factor 8,
learning rate 3e-4 and exactly 480 optimizer updates. The model architecture and
runtime-neutral tensor contract are unchanged.

The evaluator `tools/evaluate_mozart_conditioning_dose_response.py` replaces the
single 0.1↔0.9 teacher-forced probe with levels 0.1/0.3/0.5/0.7/0.9. At the shared
low/high target divergence prefix it measures:

- signed high-target minus low-target legal probability contrast at every level;
- local slope around the neutral 0.5 point;
- monotonic consistency across the full dose curve;
- integrated absolute target-probability and target-family response relative to neutral;
- legal-distribution total variation relative to the neutral distribution;
- PyTorch/ONNX parity for target probabilities and TV.

The purpose is diagnostic: distinguish a genuinely weakened/strengthened conditioning
signal from a selective response in which overall distribution TV shrinks while the
directional preference remains meaningful. The first execution is canonical-probe
only; held-out dose-response expansion remains a follow-up if the canonical curves
are stable.

The clean execution is workflow `37219415992` at branch commit
`ee705e57bb2d3bc6019e0dd850eb94066398d158`. An initial attempt failed only on a
unit-test harness omission; the assertion was corrected in `f8f8620c` and the
experiment was retriggered. The current rerun has not yet produced scientific
measurements.

The latest rerun also aligns the matched and target/context-diverse fits to identical deterministic single-threaded CPU execution. The matched fit already used `--deterministic`; the diverse fit was corrected to use the same flag. This is a reproducibility correction only and does not change the architecture, optimizer settings, fixture, probes, tensor contract, Android integration or production checkpoint boundary.
