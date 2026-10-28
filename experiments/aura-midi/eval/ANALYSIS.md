# Mozart — Baseline-vs-Fine-Tuned Generation Evaluation

**Date:** 2026-10-27
**Evaluator:** `evaluate_models.py` (new, repo root)
**Run:** `experiments/aura-midi/eval/runs/eval-matched-20261027/`
**Report:** `evaluation_report.json` (machine-readable, full provenance)
**24 MIDI samples:** 12 matched prompts × 2 models (baseline + fine-tuned)

## Setup (matched conditions)

| Item | Value |
|------|-------|
| Tokenizer | `shikhr/music_maker` (official), vocab 12,000, revision sha256 recorded |
| Pretrained checkpoint | `model.safetensors`, sha256 `38e1083a…` (matches official pretrained SHA) |
| Fine-tuned checkpoint | `pilot-20261027_145544/checkpoints/checkpoint_best.pt`, step 500, best val 2.4509 |
| Decoding | max_new=100, temperature=1.0, top_k=40, seed=20261027 (same as pilot) |
| Prompts | 12 fixed prompts (6 NRG-CP chord-oriented + 6 GMD drum-oriented), validation material only |
| Seeds | Deterministic per prompt, identical across both models (matched conditions) |
| Device | GTX 1650 (CUDA), models loaded sequentially to stay in memory budget |

## Result: the fine-tuned model DEGRADED generation

Lower validation loss did **not** translate to better music. The 500-step fine-tune on NRG-CP+GMD collapsed the model's generative behaviour:

| Metric | Pretrained | Fine-tuned | Delta (ft − pre) |
|--------|-----------|------------|------------------|
| Avg notes | 82.6 | 46.2 | −36.4 |
| Prompts with 0 notes | 0 | 2 | — |
| Prompts with ≤1 note | 0 | 5 | — |
| Avg duration (beats) | 18.2 | 13.4 | −4.8 |
| Avg duration (sec) | 9.5 | 6.8 | −2.7 |
| Note density (notes/beat) | 5.34 | 2.52 | −2.82 |
| Avg max polyphony | 6.75 | 6.42 | −0.33 |
| Avg pitch range | 38–72 | 31–47 | narrower |
| Avg velocity range | 66–110 | 63–86 | narrower, quieter |
| Avg silence (beats) | 6.21 | 6.77 | +0.56 |
| Avg repeat-bigram fraction | 0.51 | 0.28 | −0.22 |

### By source

- **GMD (drum-oriented):** catastrophic. avg notes −56.8, density −5.0, polyphony −7.8. Five of six drum prompts produced 0–1 note (premature termination / silence). Examples: `gmd-08` 54→0 notes, `gmd-10` 43→0 notes, `gmd-06` 71→1 note.
- **NRG-CP (chord-oriented):** degraded but still musical. avg notes −16.0, density −0.59, but max polyphony **+7.2** (suspicious sustained/overlapping notes) and silence **+4.3 beats**. Velocities collapsed to a narrow 87–95 band on several prompts (e.g. `nrgcp-00` 87–103 → 87–95; `nrgcp-03` 87–111 → 7–103).

### Duration discrepancy (investigated)

The historical "before vs after" figures (117 notes / 106 ticks → 119 notes / 24 ticks) are consistent with degradation, not improvement. Under my controlled, TPQ-normalized comparison (musical time in beats **and** seconds), the fine-tuned model produces shorter, sparser sequences and frequently terminates prematurely (0–1 notes = essentially silence). The old samples were not a valid A/B test because they were single prompts without recorded matched decoding conditions; this evaluation fixes that.

## Tokenizer fidelity (separate question)

Tokenizer round-trip on 8 validation MIDIs: **note count matches on all 8, token count matches on all 8.** The tokenizer faithfully represents and reconstructs MIDI (including the TPQ 96→8 rescaling, verified correct in musical time). Therefore the degradation is a **model-quality** problem, not a tokenizer problem — keeping the two questions separate as required.

All 24 generated MIDI files are valid and reopenable (symusic). MIDI timing normalized across TPQ values (tested 24/96/384/1024 → identical beats/seconds).

## What this means for the next experiment

The fine-tune overfit/collapsed on the small NRG-CP+GMD set: validation loss improved (2.4509) while generation quality fell off a cliff, especially for drums. This is a strong signal of **catastrophic forgetting / overfitting on limited data**, not a path to broader electronic coverage.

The next training experiment should therefore **not** simply run longer. Recommended direction, prioritized by evidence:

1. **Protect against catastrophic forgetting** — lower learning rate, far fewer steps (or early stopping on held-out generation quality, not just loss), and/or replay of pretrained data. Track performance separately by source (NRG-CP vs GMD) — GMD is clearly the weaker source.
2. **Address rhythmic diversity / premature termination** — the drum collapse is the most urgent measurable limitation.
3. **Broaden the data mixture** — NRG-CP (chords) + GMD (drums) alone do not establish broad electronic-subgenre coverage (techno, house, trance, dnb, dubstep, ambient, electro, breaks). Do not claim genre control without authoritative labels.

Do not launch another long training run or download a large dataset until the experiment's data mixture, objective, validation strategy, and measurable success criteria are defined. Success should be measured by generation quality (note density, polyphony, pitch/velocity diversity, silence, premature termination), not validation loss alone.

## Evidence classification

- **VERIFIED** — checkpoint hashes, pilot metrics, tokenizer round-trip, all 24 generations, 14 unit tests, this comparison (computed from the generated report in this session).
- All prior "REPORTED, NOT VERIFIED" pilot claims (loss values, VRAM, token counts) were cross-checked against the artifacts in `experiments/aura-midi/runs/pilot-20261027_145544/` and match.
