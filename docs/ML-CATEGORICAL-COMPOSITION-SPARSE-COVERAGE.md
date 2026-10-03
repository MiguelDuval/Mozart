# Sparse multi-axis categorical composition experiment

Status: development-only diagnostic.

## Hypothesis

The single-axis-only experiment showed that unseen multi-axis categorical
conditioning changes the model output, while interaction residual grows with
the number of simultaneous axes. Before changing the conditioning architecture,
test whether sparse exposure to multi-axis combinations improves this behavior.

## Controlled intervention

Baseline fixture:

- 20 training records;
- 10 validation records;
- 20 test records;
- 480 optimizer updates;
- seed 42;
- 12 epochs;
- batch size 4;
- fit-diagnostic mode;
- learning rate 3e-4.

Sparse-coverage fixture:

- 32 training records;
- 10 validation records;
- 20 identical held-out test records;
- the same model/configuration and optimizer;
- the same 480 optimizer updates;
- seed 42;
- repeat factor changed from 8 to 5 so training exposure remains exactly 480 updates.

The additional 12 training records are six two-axis combinations, each observed
in the same two training contexts:

- style + substyle
- style + role
- substyle + mood
- mood + role
- substyle + rhythm
- rhythm + role

These axis sets are disjoint from every held-out test composition. Therefore the
intervention adds composition coverage without directly training on any test
profile.

## Measurement

The existing composition evaluator is unchanged. It measures:

- teacher-forced distribution shift;
- grammar-constrained autoregressive sequence divergence;
- logit-space interaction residual;
- actual-vs-additive cosine;
- PyTorch/ONNX parity.

The test fixture itself is unchanged, so the baseline and sparse-coverage reports
are directly comparable.

## Interpretation rule

A useful outcome would be a consistent reduction in interaction residual and/or
more stable autoregressive behavior on held-out compositions without introducing
a new architecture change.

A null or unstable result means the next experiment should investigate training
regime/conditioning fusion rather than immediately changing production code.

This experiment does not establish real musical semantics because the fixture
renderer is synthetic and deliberately additive.
