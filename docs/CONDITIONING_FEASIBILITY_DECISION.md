# Conditioning Feasibility Decision — Mozart

**Date:** 2026-10-21  
**Status:** Decision recorded; corrected asset-level sidecar scan still required locally  
**Scope:** Broad single-stream polyphonic electronic-music generation  
**Decision:** **NO-GO for genre/section conditioning today; NO vocabulary expansion.**

## 1. Evidence basis and correction

The local corpus scan reported:
- NRG-CP: 15,235 MIDI files described as algorithmic EDM chord progressions. Source semantics support a **Chords/Harmony** label; the flat MIDI directory makes path-derived splits unknown.
- GMD: 1,150 drum grooves with source-grounded **Drums** labels; the existing CSV gives 897 train, 124 validation and 129 test rows. Its 57 raw style strings are rhythmic/source-style metadata, not 57 electronic subgenres.
- Slakh sample: 28 metadata stem rows across 3 compositions, with instrument-class/is_drum evidence and weak functional-role candidates; one stem is reported without saved MIDI. The sample is non-commercial research-only.
- MAESTRO: 1,276 performance rows linked to 852 distinct title-like composition identifiers in the scan. **Preserve all 1,276 performance assets**; 852 is a grouping count, not a reason to discard performances. The data is CC BY-NC-SA 4.0 and must remain research-only.
- All four sources have zero reliable `genre_label` values and zero authoritative arrangement-section labels.

### Sidecar count correction

The earlier generated sidecar summary reported 17,240 rows and 449 “duplicates removed”. Code review found that the previous deduplication key was `dedup_id` (`source_id:composition_id`), which groups assets by composition rather than identifying duplicated assets. This collapsed valid Slakh stems and MAESTRO performances. Those 17,240 rows and the 449-removal count are **invalid as asset-level counts**.

The builder now deduplicates only an identical `(source_id, composition_id, asset_id)` row, retains unsaved Slakh metadata with `midi_saved=false`, and exposes source-role/style/candidate counts by split. Nine hosted unit tests pass. The corrected builder still needs to be run locally against the real files; do not treat the arithmetic expectation of 17,689 rows before true duplicate removal as a verified new output.

## 2. Label feasibility by task

| Conditioning target | Evidence currently available | Decision |
|---|---|---|
| Electronic subgenre (techno, house, trance, DnB, dubstep, ambient, etc.) | 0 authoritative genre labels across the scanned sources | **NO-GO** — adding genre tokens would fabricate supervision |
| Arrangement section (intro, verse, build, breakdown, drop, outro) | 0 authoritative section labels | **NO-GO** — do not invent structure labels |
| Functional role within a full arrangement | NRG-CP provides chord-sequence semantics; GMD provides drum-groove semantics; Slakh roles are weak candidates across only 3 compositions; MAESTRO Piano is instrument identity, not functional role | **NO-GO for broad production conditioning** |
| Narrow source-specific role experiment | 15,235 NRG-CP chord examples (split currently unknown) and 1,150 GMD drum examples (known file-level split) | **Potential future research experiment**, not an implemented capability and not evidence of role control in the trained model |
| Single-stream polyphony | Chord progressions and drum sequences are represented, but quality and broad electronic coverage are not established by metadata counts | Continue as the modelling priority; use controlled generation/evaluation when checkpoint access is available |

The presence of a sidecar label is not model conditioning. Phase 1 was not trained with a validated conditioning interface, and the 12,000-token checkpoint cannot consume new token IDs without a deliberate, tested model/tokenizer version change.

## 3. Architecture decision

1. Preserve the current official REMI+BPE 12,000-token model and Phase 1 checkpoint as the unchanged baseline.
2. **Do not add role, genre, section, track, or other tokens now.** No evidence shows that new vocabulary would address the dominant gap: missing genre/section supervision and a lack of complete electronic arrangements.
3. Keep labels out of the token stream until a specific control task and acceptance test are defined. If a later experiment has sufficient examples, compare a small out-of-band conditioning mechanism (for example a separate learned condition embedding) against an unconditioned baseline; this would be a separately versioned model change and needs safe checkpoint access, train/validation separation, and fixed-seed evaluation.
4. Do not mix NC/NC-SA sources into a production-oriented path. Keep their assets, derived checkpoints and experiments explicitly segregated as research-only. For CC BY sources, maintain attribution and independently verify provenance before treating the full model pipeline as commercially cleared.

## 4. Required next steps

1. **Regenerate the sidecar locally with the corrected builder.** Verify 28 Slakh metadata rows remain distinguishable by composition + stem ID; verify the 1,276 MAESTRO performance rows remain, while the title-like grouping count is reported separately. Inspect missing paths and actual duplicate rows.
2. Inspect the existing local NRG-CP audit/Phase 1 manifests for original train/validation/test file membership and map those memberships into the sidecar if reliable per-file IDs are available. Do not infer split labels from the flat directory, and do not randomly split after training windows have already been created.
3. Reconfirm per-source and per-split counts from the corrected JSONL/summary. If the NRG split cannot be reconstructed, explicitly retain `unknown` and do not claim held-out evaluation for those examples.
4. Make the next data-acquisition choice based on the dominant gap: an ethically and legally suitable corpus with explicit electronic-subgenre labels and/or full-track multi-instrument MIDI arrangements. Check composition-level uniqueness, train/validation/test identity, attribution, and commercial eligibility before downloading or training.
5. Return to conditioning architecture only when label coverage and a measurable control objective justify it.

## 5. Safety and scope

This decision does not authorize model training, checkpoint loading, downloads, token changes, reboot, process termination, or merge of PR #3. No reboot. No changes to `main`.


## External data screening reference

The initial external corpus screen is documented in `docs/EXTERNAL_DATASET_CANDIDATES.md`. It found a small multi-track electronic dataset useful for research-only structural evaluation, but no verified source that meets both broad electronic coverage and production-oriented rights requirements. No files were downloaded.
