This file is an explicit audit marker for the corrected v2 multi-seed context-diversity replication.

The accompanying commit message contains [run-diversity-replication]. The research workflow consumes this marker only on feature branches; ordinary ML/Android workflows do not include this path in their triggers.

Seeds: 7, 42, 123.
Design: matched exposure vs context-diverse, 480 optimizer updates per fit, corrected v2 fixture, 10 train / 4 validation / 2 test base contexts, canonical five-control probes.
Next gate: evaluate conditioning on four contexts excluded from training, 20 low/high control probes, across seeds 7/42/123.

Trigger revision: held-out conditional probe suite wired into replication workflow.

Trigger revision: sequence report summarizer now derives held-out metrics from per-control evaluator output.
Trigger revision: seed summary is rewritten after held-out aggregation so the cross-seed job receives held-out metrics.
Trigger revision: target-fixed conditioning-context control arm; diversify model-visible categorical context while freezing target tokens and performance controls.

Factorial revision: run corrected 2x2 target/conditioning decomposition with a true joint arm; target-only is canonicalized from that joint arm to avoid the historical no-op.
Run seeds: 7, 42, 123.

