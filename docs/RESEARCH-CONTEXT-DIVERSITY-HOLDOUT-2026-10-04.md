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

The full three-seed run is 37186038694; results are recorded below only after
the run and all gates complete.

## Next scientific gate

The current evidence separates two effects that were previously conflated: better
held-out generalization and stronger conditional responsiveness. The next minimal
experiment should therefore isolate the causal mechanism of the diversity gain,
not change the model architecture.

Use a third, matched-exposure control arm in which the conditioning metadata is
made context-diverse while the target MIDI/token sequence exposure is held fixed.
Keep the same four validation contexts, five controls, three seeds, 480-update
budget, optimizer settings, and evaluation suite. Compare this arm against the
existing matched and context-diverse arms.

The question is narrow: does the generalization/held-out response improvement
survive when only the conditioning context coverage changes, or does it require
additional target-sequence diversity as well? Until that is answered, no
architecture, tensor ABI, or production-checkpoint decision should be based on
this synthetic result.
