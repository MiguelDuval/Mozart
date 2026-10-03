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

## Next scientific gate

The remaining ambiguity is whether conditioning responsiveness generalizes to
contexts that were not part of the training probe set. The next useful experiment
is therefore an evaluation-only held-out conditional probe suite: for each of the
four validation contexts, vary each performance control while holding the other
four controls fixed, and measure teacher-forced target response plus
grammar-constrained distribution response. Those probes should remain outside
training and should be scored separately from the canonical train-context probes.

No production model or ONNX tensor ABI should be frozen before that gate.
