This file is an explicit audit marker for the corrected v2 multi-seed context-diversity replication.

The accompanying commit message contains [run-diversity-replication]. The research workflow consumes this marker only on feature branches; ordinary ML/Android workflows do not include this path in their triggers.

Seeds: 7, 42, 123.
Design: matched exposure vs context-diverse, 480 optimizer updates per fit, corrected v2 fixture, 10 train / 4 validation / 2 test base contexts, canonical five-control probes.
Rerun marker: corrected fixture-cardinality test before the held-out-context replication.
