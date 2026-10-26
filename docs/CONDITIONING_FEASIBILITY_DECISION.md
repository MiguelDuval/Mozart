# Conditioning Feasibility Decision — Mozart

**Date:** 2026-10-21  
**Status:** Corrected asset-level sidecar scan reported complete by Cline; next-step training decision recorded  
**Scope:** Broad single-stream polyphonic electronic-music generation  
**Decision:** **NO-GO for genre/section conditioning today; NO vocabulary expansion.**

## 1. Evidence basis and correction

The local corpus scan reported:
- NRG-CP: 15,235 MIDI files described as algorithmic EDM chord progressions. Source semantics support a **Chords/Harmony** label; the corrected scan restored splits from the Phase 1 data index: train=13,711, validation=761, test=763.
- GMD: 1,150 drum grooves with source-grounded **Drums** labels; the existing CSV gives 897 train, 124 validation and 129 test rows. Its 57 raw style strings are rhythmic/source-style metadata, not 57 electronic subgenres.
- Slakh sample: 32 stem metadata rows across 3 compositions (28 marked as saved MIDI and 4 marked unsaved); the scan reports 5 missing MIDI paths. Instrument-class/is_drum roles remain weak candidates. The sample is non-commercial research-only.
- MAESTRO: 1,276 performance rows linked to 852 distinct title-like composition identifiers. **Preserve all 1,276 performance assets**; 852 is a grouping count, not a reason to discard performances. The data is CC BY-NC-SA 4.0 and any run using it must remain research-only.
- All four sources have zero reliable `genre_label` values and zero authoritative arrangement-section labels.

### Sidecar count correction

The earlier generated sidecar summary reported 17,240 rows and 449 “duplicates removed”. Code review found that the previous deduplication key was `dedup_id` (`source_id:composition_id`), which groups assets by composition rather than identifying duplicated assets. This collapsed valid Slakh stems and MAESTRO performances. Those 17,240 rows and the 449-removal count are **invalid as asset-level counts**.

The builder now deduplicates only an identical `(source_id, composition_id, asset_id)` row, retains unsaved Slakh metadata with `midi_saved=false`, and exposes source-role/style/candidate counts by split. Cline reports the corrected local scan at 17,693 asset records: 15,235 NRG-CP + 1,150 GMD + 32 Slakh metadata rows + 1,276 MAESTRO performance rows; 0 duplicate asset rows removed. The result is recorded in `experiments/aura-midi/audit_report.json`. Nine hosted unit tests pass. Treat these as locally reported evidence from Cline, not independent execution by ChatGPT.

## 2. Label feasibility by task

| Conditioning target | Evidence currently available | Decision |
|---|---|---|
| Electronic subgenre (techno, house, trance, DnB, dubstep, ambient, etc.) | 0 authoritative genre labels across the scanned sources | **NO-GO** — adding genre tokens would fabricate supervision |
| Arrangement section (intro, verse, build, breakdown, drop, outro) | 0 authoritative section labels | **NO-GO** — do not invent structure labels |
| Functional role within a full arrangement | NRG-CP provides chord-sequence semantics; GMD provides drum-groove semantics; Slakh roles are weak candidates across only 3 compositions; MAESTRO Piano is instrument identity, not functional role | **NO-GO for broad production conditioning** |
| Narrow source-specific role experiment | 15,235 NRG-CP chord examples with restored split membership and 1,150 GMD drum examples with file-level splits | **Potential research experiment**, not an implemented capability and not evidence of role control in the trained model |
| Single-stream polyphony | Chord progressions and drum sequences are represented, but quality and broad electronic coverage are not established by metadata counts | Continue as the modelling priority; use controlled generation/evaluation when checkpoint access is available |

The presence of a sidecar label is not model conditioning. Phase 1 was not trained with a validated conditioning interface, and the 12,000-token checkpoint cannot consume new token IDs without a deliberate, tested model/tokenizer version change.

## 3. Architecture decision

1. Preserve the current official REMI+BPE 12,000-token model and Phase 1 checkpoint as the unchanged baseline.
2. **Do not add role, genre, section, track, or other tokens now.** No evidence shows that new vocabulary would address the dominant gap: missing genre/section supervision and a lack of complete electronic arrangements.
3. Keep labels out of the token stream until a specific control task and acceptance test are defined. If a later experiment has sufficient examples, compare a small out-of-band conditioning mechanism (for example a separate learned condition embedding) against an unconditioned baseline; this would be a separately versioned model change and needs safe checkpoint access, train/validation separation, and fixed-seed evaluation.
4. Do not mix NC/NC-SA sources into a production-oriented path. Keep their assets, derived checkpoints and experiments explicitly segregated as research-only. For CC BY sources, maintain attribution and independently verify provenance before treating the full model pipeline as commercially cleared.

## 4. Immediate Training Decision

**Do not wait for genre/section labels before doing an unconditioned next-token experiment.** Missing labels block trustworthy genre/section conditioning, but do not block ordinary language-model fine-tuning. Phase 1 is already a 25,000-step trained baseline. The next useful deliverable is a controlled single-stream polyphony experiment and listening-ready MIDI examples, not another documentation-only phase.

1. Inspect the current Windows/PyTorch state once. Do not assume old PIDs still exist, do not terminate unrelated processes, and do not reboot.
2. Try one bounded checkpoint-load smoke test. If it succeeds, preserve the Phase 1 checkpoint and start a new research-only run from a copy/state loaded into a separate output directory, using the original 12,000-token tokenizer. Use NRG-CP/GMD replay and MAESTRO train examples as a controlled polyphony supplement, with per-source validation metrics. Because MAESTRO is CC BY-NC-SA 4.0, this experiment and its resulting checkpoint must be labelled **research-only / non-commercial**. Filter MAESTRO composition IDs that overlap its validation/test split out of training.
3. Do not train on Slakh's three compositions; use the 32 stem metadata rows for inventory/codec research only.
4. Run a 10,000-step controlled fine-tune with evaluation every 500 steps and early stopping; save best/last checkpoints atomically in a new run directory. Keep source-specific validation metrics and generate fixed-seed MIDI samples before and after. Do not overwrite the Phase 1 best checkpoint.
5. If checkpoint loading still hangs on the first bounded attempt, do not loop retries or reboot. Verify whether a tiny fresh-process tensor/forward-backward step works. If it does, report the exact minimal blocker and make a practical fallback decision; do not silently replace the baseline with a randomly initialized model.
6. Continue dataset acquisition after this experiment. This run is an incremental polyphony research result, **not** a claim of broad electronic-subgenre mastery.

## 5. Required follow-up

1. Record actual training command, run directory, starting checkpoint SHA, config, seed, data ratios, and license status.
2. Compare starting and ending checkpoints on the same fixed-seed prompts and decoding settings. Validate MIDI files and report note density, overlap/polyphony, pitch range, duration, repetition, and listening evidence if available.
3. Do not call the result successful based only on a lower validation loss; inspect actual generated MIDI and per-source metrics.
4. If the checkpoint-load blocker remains, stop the training attempt after one bounded test, preserve all artifacts, and report it as BLOCKED rather than conducting another audit loop.

## 6. Safety and scope

This decision authorizes the isolated research-only experiment described above only after the bounded runtime/checkpoint gate succeeds. It does not authorize changes to tokens/model dimensions, large downloads, reboot, terminating unrelated or privileged processes, or merging PR #3. No reboot. No changes to `main`.


## External data screening reference

The initial external corpus screen is documented in `docs/EXTERNAL_DATASET_CANDIDATES.md`. It found a small multi-track electronic dataset useful for research-only structural evaluation, but no verified source that meets both broad electronic coverage and production-oriented rights requirements. No files were downloaded.


---

## Training Gate Addendum — 2026-10-26

Cline reports that a 174 MB artifact at `experiments/aura-midi/weights/auramidi_v1.pt` loaded in a local CPU-only PyTorch 2.14.1 environment and passed one fresh-process forward/backward/optimizer step. The report gives 12 layers, vocab=12,000, n_embd=512, n_head=8, block_size=1,024 and 50.6M parameters. These are **reported local results**, not independently reproduced by ChatGPT.

The 533 MB checkpoint at `experiments/aura-midi/runs/broad-training-20261020_204942/checkpoint_best.pt` still reportedly hangs on its one attempted load. It was not retried and remains untouched. The successful smaller artifact must not be treated as equivalent to that fine-tuned checkpoint by filename or size.

**Updated decision: PARTIAL PASS.** A single optimizer step proves basic execution for the smaller file, not the larger checkpoint's loadability, model/tokenizer lineage, full training viability, or musical improvement. Before any long run, verify the saved model config, all embedding/head tensor shapes, input/output weight-tying behavior and exact tokenizer ID mapping. The reported 50.6M parameters differ from the previously recorded 44.43M architecture, so this difference requires an explicit explanation.

Once compatibility is verified, perform a bounded, timed CPU pilot in a separate research directory. Record actual optimizer steps and throughput, preserve fixed-seed generated MIDI before/after, use per-source validation and atomically save outputs. Do not add vocabulary tokens or switch to MMM v2. The pilot's dataset and checkpoint remain subject to the existing license restrictions; MAESTRO means research-only/non-commercial. No reboot, no retry of the blocked 533 MB load, and no overwrite/deletion of checkpoints.
