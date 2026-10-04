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

## Corrected 2x2 factorial gate (in progress)

The current branch now implements the planned four-arm causal decomposition without changing
the model architecture, tensor ABI, Android integration or production checkpoint.

The previous `context-diverse` fixture arm is treated as a **historical target-only arm**:
its ten added training positions vary target MIDI/render identity while the five
model-visible categorical conditioning fields remain canonical. It is therefore not a
valid "both target + conditioning" arm.

The corrected factorial uses:
1. **Matched** — target fixed + conditioning fixed.
2. **Target-only** — target diverse + canonical conditioning, constructed from the joint
   exposure and forced back to canonical conditioning.
3. **Conditioning-only** — target fixed + conditioning diverse, the existing target-fixed
   causal control.
4. **Both / joint** — target diverse + conditioning diverse, a new joint arm.

All arms retain 20 train positions, four completely unseen validation contexts, the same
five control probes, seeds 7/42/123, batch size 4, repeat factor 8, learning rate 3e-4
and exactly 480 optimizer updates.

The corrected joint builder enforces unchanged target tokens, target SHA-256 values,
source paths, performance controls and conditioning seeds, while applying only the
five model-visible conditioning fields on the ten context-diverse variants. The
target-only builder now refuses canonical-conditioning input, preventing the historical
no-op control from being silently accepted.

Implementation commits on `feature/link-clock`:
`f7f92991`, `87e682b4`, `e9402266`, `4fcd79af`, `750cbf2a`,
`104027ed`, `92df0732`, `cc442c88`, `2986b85d`, `4715ff29`,
`c706e6a6`.

The active corrected replication run is `37207001692` at commit
`c706e6a59e23b059ecd5c0bfdc9681d31002795b`. Its unit/contract gates have passed
and the three seed jobs are currently in the multi-arm training phase. No scientific
claim from this corrected factorial is recorded here until the seed and aggregate
results complete successfully.

