This file is an explicit audit marker for the conditioning dose-response experiment on mozart-conditioning-fixture-v2.

Design: matched-exposure vs target/context-diverse, seeds 7/42/123, 20 train positions per arm, batch size 4, repeat factor 8, learning rate 3e-4, exactly 480 optimizer updates.

Dose levels: 0.1, 0.3, 0.5, 0.7, 0.9.
Primary measurement: shared-prefix low-target vs high-target legal-token probability contrast.
Secondary measurements: slope around neutral, monotonic consistency, integrated absolute target/family response, and legal-distribution TV from neutral.

This experiment is diagnostic-only. It does not freeze the production tensor ABI, change Android integration, or select a production checkpoint.

Retry: corrected the dose-response monotonic-fraction unit assertion before rerunning the experiment.

Retry 2: corrected remaining monotonic-fraction test call sites before dose-response execution.
Rerun requested at: 2026-10-04T18:10Z

Retry 3: rerun requested after the latest monotonic-fraction test-callsite repair.

Retry 4: aligned matched and diverse fits to identical deterministic CPU execution before the scientific rerun.

Retry 5: rerun after making each seed artifact self-auditing and validating identical fit contracts across arms.
