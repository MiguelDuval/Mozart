# Sparse categorical composition seed replication

Status: development-only diagnostic evidence.

## Controlled experiment

The sparse-coverage fixture is unchanged from the seed-42 sparse experiment:

- 32 train records: 20 single-axis + 12 multi-axis records;
- 10 validation records and 20 held-out test records, unchanged across runs;
- six additional pair profiles, each in two training contexts;
- 480 optimizer updates per fit;
- 12 epochs, batch size 4, repeat factor 5, learning rate 3e-4;
- fit-diagnostic mode, CPU;
- model `mozart-symbolic-transformer-v0`, 32,820,480 parameters;
- seeds 42, 1337, 2027;
- PyTorch 2.14.0+cpu and ONNX evaluation retained.

All three seed fits were executed sequentially on one GitHub Actions runner. Every evaluator returned diagnostic `PASS`, with PyTorch/ONNX parity below 1e-4 for the reported probes.

## Additional repeatability probe

A separate diagnostic run trained the exact sparse configuration twice sequentially on one runner with the same seed 42.

Both runs produced identical:

- epoch train/validation traces;
- selected epoch = 3;
- selected validation loss = 3.500037511189779;
- canonical best-model SHA256;
- canonical latest-model SHA256.

Environment recorded by the probe:

- torch = 2.14.0+cpu;
- torch threads = 2;
- torch inter-op threads = 4;
- OMP/MKL thread overrides unset.

Therefore the earlier difference between sparse run #1 and #2 is not explained by ordinary intra-run stochastic drift. It is an inter-runner/environment sensitivity signal. The two earlier runs used different GitHub Actions runner IDs.

## Teacher-forced generalization

Baseline selected validation loss: 5.349342 at epoch 2.

Sparse selected validation losses:

- seed 42: 3.549207 at epoch 3;
- seed 1337: 3.239421 at epoch 3;
- seed 2027: 3.139063 at epoch 3.

The seed mean is about 3.30923, approximately 38.1% below the baseline validation loss.

This is evidence that the extra multi-axis coverage improves teacher-forced generalization to the held-out multi-axis validation set. It does not establish autoregressive robustness or real musical quality.

## Held-out compositional diagnostics

| Held-out composition size | Baseline AR mean TV | Sparse seed mean AR mean TV | Baseline interaction residual | Sparse seed mean interaction residual | Baseline additive cosine | Sparse seed mean additive cosine | Baseline TF TV | Sparse seed mean TF TV |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 axes | 0.365804 | 0.724651 | 0.113318 | 0.100199 | 0.994863 | 0.996676 | 0.243296 | 0.375969 |
| 3 axes | 0.393130 | 0.799947 | 0.207748 | 0.187287 | 0.982885 | 0.992594 | 0.277442 | 0.493423 |
| all 5 | 0.457954 | 0.851361 | 0.445510 | 0.376594 | 0.911709 | 0.975620 | 0.313407 | 0.611649 |

Relative to baseline, sparse multi-axis coverage lowers mean interaction residual by about 11.6% (2-axis), 9.8% (3-axis), and 15.5% (all-five), while additive-cosine alignment also increases, most strongly for all-five.

The profile-level result is not uniformly stable:

- interaction residual is lower than baseline for all three seeds on 3 of the 10 held-out profiles;
- by seed, the number of improved profiles is 5/10 (42), 10/10 (1337), and 7/10 (2027);
- for the all-five profile, interaction residual is 0.448270 (seed 42), 0.352676 (seed 1337), and 0.328834 (seed 2027), versus baseline 0.445510.

So the compositionality signal improves in aggregate, but not strongly enough to call full profile-level generalization solved.

## Autoregressive behavior

AR mean TV is higher than baseline on all 10 held-out profiles for all three seeds (30/30 profile-seed comparisons).

First divergence also moves earlier: in the sparse seed suite, 26 of 30 profile-seed cases diverge at generated index 0.

This demonstrates a stronger/immediate autoregressive response to categorical composition under the current grammar-constrained evaluator. It must not be described as a confirmed musical regression, because this evaluator measures conditioning-induced distribution/sequence divergence rather than target-sequence accuracy. It does, however, show that sparse coverage did not solve the current AR robustness criterion.

## Interpretation

The evidence now separates three effects:

1. **Teacher-forced generalization:** improved robustly across all three seeds.
2. **Logit-space compositional additivity:** improved on average, especially for 3- and 5-axis combinations, but not uniformly across profiles.
3. **Autoregressive conditioning behavior:** remains unresolved; the model reacts earlier and with larger TV, with no held-out profile showing lower AR mean TV than baseline in any of the three seeds.

The data-coverage hypothesis therefore has positive evidence in teacher-forced/generalization and additive logit structure, but it is not yet sufficient to claim robust compositional conditioning end-to-end.

The synthetic renderer is additive by construction, so interaction residual remains a structural diagnostic only; it is not evidence of musical semantic compositionality.

## Next experiment

Do not change the production architecture yet.

Before moving to conditioning-fusion changes, run a controlled coverage-dose experiment that keeps the held-out validation/test set fixed and the 480-update budget fixed. The cleanest next comparison is to increase multi-axis coverage from the current six pair profiles toward complete pairwise coverage, while keeping all other training/evaluation settings unchanged.

Because sparse coverage also changes the repeat factor (8 -> 5) and unique-record count (20 -> 32), the dose experiment should be interpreted as a training-coverage intervention rather than a pure one-variable architectural test. A matched-size single-axis control can be added if the next result still needs attribution between "more records" and "more multi-axis coverage".

No production Android, ABI, scheduler, Ableton Link, AMidi, or realtime MIDI code is involved in this diagnostic.
