# Categorical conditioning composition diagnostic

Status: development-only diagnostic. These fixtures are synthetic and are not
production training data.

## Purpose

The current Mozart Transformer injects five categorical embeddings additively
at the input of the causal Transformer:

- style
- substyle
- mood
- rhythm
- role

This experiment asks a narrower question: after training only on single-axis
categorical variants, does the model respond to previously unseen combinations
of two, three, and five axes?

## Baseline fixture

Revision: `mozart-categorical-composition-fixture-v1`

Training contains 20 records: for each categorical axis, both base and high
values are exposed in two held-out-context seeds. No training example contains
more than one high categorical axis.

Validation contains 10 unseen multi-axis combinations.

Test contains 20 records: a base/control pair and the corresponding unseen
multi-axis combination for each of 10 composition profiles. Test context is
held out.

The synthetic renderer deliberately uses additive categorical shifts. Therefore
the experiment is primarily a conditioning-capacity/composition diagnostic; it
does not establish real musical genre semantics.

## Baseline run

Commit: `9d01ac91820e368276784e066dddb1a86f73e593`

Workflow: `37141431741`

Training selected the validation-best checkpoint at epoch 2:

- train loss: 2.159657
- validation loss: 5.349342
- optimizer updates: 480

PyTorch/ONNX parity remained below 1e-4 in all reported probe paths.

All ten unseen composition probes changed the grammar-constrained autoregressive
sequence. Mean autoregressive total variation increased from approximately
0.366 for two-axis combinations to 0.393 for three-axis combinations and 0.458
for the all-five combination.

The logit-space additive interaction residual ratio was approximately:

- two axes: 0.113
- three axes: 0.208
- all five axes: 0.446

For the all-five probe, actual-vs-additive logit cosine was approximately 0.912.

These numbers are diagnostic measurements, not quality scores or production
gates.

## Interpretation

The baseline demonstrates that the current categorical pathway can produce
distinct responses to unseen multi-axis conditioning. It also shows increasing
non-additive interaction as more axes are combined.

The result does not distinguish between:

1. insufficient multi-axis training coverage,
2. expected nonlinear interaction created by the Transformer,
3. instability from the tiny synthetic training regime.

The next controlled intervention is therefore data coverage before architecture
changes: expose a sparse set of multi-axis training combinations while keeping
the same model, fixture style, and fixed optimizer-update budget. Compare the
same held-out two/three/five-axis probes and the same logit interaction metrics.

A separate reproducibility branch tests seed sensitivity before that intervention.
