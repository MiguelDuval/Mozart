# Broad Polyphonic Model Plan — Mozart

**Status:** Next-work plan; no new training run authorized by this document.  
**Created:** 2026-10-21  
**Branch:** `feature/mmm-v2-decoder-fix-and-docs`  
**Strategic scope:** Broad electronic-music generation, with single-stream polyphony as the near-term model priority.

## 1. Decision

The current Phase 1 broad-training checkpoint remains the working research baseline. The immediate objective is **not** to make MMM v2 multi-track training mandatory. It is to improve a single-stream symbolic model's ability to generate polyphonic electronic-music material across a wide range of styles.

Polyphony means that one MIDI track/stream may contain overlapping notes and chords. Multi-track modelling means separately preserving and generating several instrument parts. These are not the same requirement. Multi-track arrangement generation remains an optional future capability and should be pursued when data and use-cases justify its added complexity.

## 2. Baseline and evidence

Reported Phase 1 artifacts:
- Checkpoint: `experiments/aura-midi/runs/broad-training-20261020_204942/checkpoint_best.pt`
- Reported best checkpoint step: 24,750.
- Reported best validation loss: 1.0252.
- Training mixture: NRG-CP (harmony/chord progressions) and GMD (drum performances).
- Reported corpus counts: 14,608 MIDI files, 15,260 train windows, 960 validation windows.
- These values must be cross-checked against saved manifests/metrics before being treated as independently verified.
- Existing official tokenizer: REMI+BPE, 12,000-token vocabulary.
- MMM v2 adds custom IDs 12000–12003 but is a separate experimental tokenizer path; it should not be substituted into Phase 1 without a compatible model/tokenizer configuration.

The reported loss reduction is encouraging but is not proof of better music. A fair baseline should be generated and evaluated using the same prompts, seed, decoding settings, and MIDI validator as any future candidate.

## 3. Current constraints

- PyTorch checkpoint loading is reported blocked by three unkillable Python processes (PIDs reported by Cline: 19992, 20436, 20600). Recheck current process identity before assuming these PIDs still exist.
- No reboot is permitted. Do not issue shutdown/restart commands or create restart tasks.
- The Phase 1 checkpoint must remain untouched.
- MMM v2's round-trip status remains **PARTIAL**: one of three samples was only partly restored; one decode timed out; one was not decoded. The known drum note-count discrepancy is material. Do not label the decoder fully verified.
- Slakh mirror samples are currently reported as only 3 compositions available and licensed CC BY-NC 4.0. This is too small for a long run and research-only.
- MAESTRO is CC BY-NC-SA 4.0 and primarily classical piano. Keep it separate from any production-oriented path.
- NRG-CP and GMD fill important roles but do not establish broad genre coverage on their own.

## 4. Phase A — Evidence-only baseline inventory (do now)

This phase must not require `torch.load()` and must not repeat already completed checks without a concrete reason.

1. Read existing manifests and metric JSON files to record actual counts and sources.
2. Summarize source diversity by unique composition, not raw file/window count.
3. For each source, record reliable genre labels, role/instrument content, license, duplicates, and coverage gaps.
4. Separate confirmed genre labels from inferred or unknown labels; never guess genre from tempo alone.
5. Index existing generated MIDI and reports. If MIDI files can be inspected without importing PyTorch, gather structural statistics: notes, duration, pitch range, tempo, tracks, and repetition indicators.
6. Preserve source-level train/validation/test splits and check existing manifests for composition overlap. Avoid a new exhaustive filesystem scan if saved manifests answer the question.

Deliverable: a concise, evidence-based coverage matrix that answers which musical roles and genre families are represented, which are missing, and which source is the best candidate to address each gap.

## 5. Phase B — Assess single-stream polyphonic generation

Use the original official tokenizer and Phase 1 model configuration as the default path. Do not use MMM v2 custom tokens for this task unless a concrete requirement proves the original tokenizer unsuitable.

Clarify acceptance criteria:
- One MIDI stream/track may contain multiple simultaneous notes.
- Chords, melodies, arpeggios, bass-like sequences and note overlap should be measured rather than assumed.
- Generated MIDI must open, contain notes, have positive duration, and use valid event timing.
- Repetition/collapse must be checked.
- Results must be compared against the base Phase 1 checkpoint with fixed prompts, seeds and generation parameters.
- Listening review is desirable when a renderer is available, but do not derail the task by installing large dependencies.

Do not call generated MIDI “high quality” merely because it is long or contains many notes. Track note density and temporal/pitch diversity separately.

If current model inference is blocked, preserve the evaluation script and existing samples and proceed with data/metadata work. Do not reboot.

## 6. Phase C — Address actual data gaps

Do not download another large dataset until Phase A identifies a specific gap.

Likely candidate gaps to investigate include:
- bass lines;
- lead/synth melodies;
- arpeggios;
- polyphonic chord voicings;
- pads/textures and ambient motion;
- breakbeat and non-four-on-the-floor rhythms;
- reliable genre diversity outside progressive/EDM chord sequences;
- full-length or coherent phrase-level MIDI rather than only short patterns.

For each candidate source, record:
- origin and version;
- license and attribution;
- genre/role coverage;
- unique composition count after deduplication;
- tokenizer compatibility;
- download size and available disk space;
- whether the data is production-eligible or research-only.

Use small representative samples before full downloads. Never add non-commercial data to a production-oriented training run without clearly isolating and labeling the experiment.

## 7. Phase D — Prepare a controlled training plan, but do not start yet

Once data diversity and checkpoint access are usable:
- keep the original Phase 1 checkpoint and tokenizer as the baseline;
- use only genuinely new, appropriate data to address measured gaps;
- retain replay from NRG-CP/GMD at a controlled ratio to reduce forgetting;
- keep examples separate by source composition;
- use validated train/validation/test manifests;
- compute token-weighted cross-entropy consistently;
- report metrics per source or genre when sample sizes allow;
- save best/last checkpoint atomically with optimizer, scheduler, and RNG state;
- validate generated MIDI and compare fixed-seed samples.

Do not assume that genre conditioning requires multi-track output. If genre conditioning becomes a priority, first determine whether trustworthy genre labels and a compatible conditioning mechanism are available. Do not add arbitrary token IDs or resize the vocabulary casually.

## 8. MMM v2 is an optional research branch

Keep `tokenizer_mmm_v2.py`, `train_mmm_v2.py`, and existing round-trip artifacts preserved.

Do not run long training on the current three Slakh samples. Do not expand the vocabulary or continue multi-track fine-tuning until:
- the decoder round-trip bug and drum-event loss are addressed;
- more unique compositions are available;
- a concrete use-case requires explicit arrangement tracks;
- model checkpoint loading works safely without reboot.

No further multi-track work is required merely to improve single-track polyphony.

## 9. Operational safety

- Never reboot or shut down the machine automatically.
- Do not kill unrelated or privileged processes.
- Do not start concurrent training processes.
- Do not repeatedly retry a known hanging checkpoint load.
- Preserve local commits, remote branches, checkpoints and partial downloads.
- Keep code, data and reports on the existing feature branch; do not push experimental changes to `main`.
- Use `docs/AI_MODEL_COLLABORATION_LOG.md` for append-only handoffs, and `docs/MUSIC_MODEL_TRAINING_HISTORY.md` for durable experiment history.
- Explicitly classify claims as VERIFIED, REPORTED/NOT VERIFIED, UNVERIFIED, or BLOCKED.

## 10. Immediate next action — Start a Controlled Experiment

The metadata-only corpus audit and split reconciliation are now reported complete by Cline. The next step is **not another audit cycle**.

Missing genre/section labels block reliable genre/section conditioning, but they do not block unconditioned next-token training. Phase 1 already exists as a 25,000-step checkpoint. Proceed with a controlled single-stream polyphony experiment as specified in `docs/CONDITIONING_FEASIBILITY_DECISION.md`:

- inspect the current PyTorch state once and perform one bounded load attempt for the Phase 1 checkpoint;
- if the checkpoint can be loaded safely, run a new 10,000-step research-only fine-tune in a new output directory, with the original 12,000-token tokenizer, source-balanced NRG-CP/GMD replay and MAESTRO as a non-commercial polyphony supplement;
- keep validation/test identity separate, explicitly filter any MAESTRO composition IDs spanning splits, evaluate every 500 steps, use early stopping, and generate fixed-seed MIDI before/after samples;
- do not overwrite the Phase 1 checkpoint and do not train on the three-composition Slakh sample;
- if checkpoint loading still hangs, do not loop retries or reboot; establish whether a tiny forward/backward operation works and report the concrete blocker.

This is an incremental research experiment, not a claim of full-spectrum electronic-genre coverage. No more preparation-only work should precede it.


---

## Decision Update — Prefer Metadata Before New Role/Section Tokens (2026-10-21)

The latest Cline local audit reports that available sources have very uneven roles: NRG-CP is chord progression material, GMD is drum grooves, and only three Slakh compositions are currently available. It reports no trustworthy electronic-subgenre labels. Treat these counts as reported until reconciled against local manifests.

Do **not** expand the vocabulary to add role or section tokens in the immediate next step.

### Why
- Role/section labels do not emerge merely by adding token IDs; examples must carry labels with meaningful semantics.
- NRG-CP and GMD have source-grounded roles. Record them as sidecar labels first.
- Slakh instrument-class metadata may support some track role labels, but three compositions are not enough for broad training.
- Pitch, velocity, program and density heuristics may propose weak role labels, but must carry confidence and rule-version metadata; unknown is a valid label.
- No authoritative intro/verse/chorus/breakdown/drop/outro labels have been identified. Do not fabricate them.
- Adding five role and six section tokens to an existing 12,004-token MMM vocabulary would yield 12,015 total, not 12,020. The Phase 1 checkpoint has a 12,000-token output space, so these new IDs cannot be used with it without a deliberately designed, tested vocabulary/model expansion.
- Track markers are not required for the near-term goal of generating a polyphonic passage in one stream.

### Next offline task
Create a source-grounded metadata labeling manifest over existing corpus manifests and file metadata. Do not import/load PyTorch, alter vocabularies, retrain BPE, download large archives or start training.

Minimum outputs:
1. Counts by source and composition, distinguishing compositions from files, tracks, windows and tokens.
2. Source-grounded role counts with provenance.
3. Reliable genre-label counts; unknown or missing labels must remain explicit.
4. Optional weak heuristic role candidates stored separately with confidence and rule version.
5. A clear report explaining whether data is sufficient for useful genre/role conditioning.
6. Current baseline MIDI inventory and structural measurements when obtainable without PyTorch.

Once this report identifies a material gap, select one small source or data transformation that fills that gap. Do not commence long training until checkpoint access works and the data is suitable.

The main objective remains broad single-stream polyphonic electronic-music generation. MMM v2 stays experimental pending complete round-trip, drum-event preservation, and a demonstrated need for explicit multi-track generation.


---

## Execution Update — Sidecar Builder Added (2026-10-21)

A reproducible metadata-only builder now exists at `experiments/aura-midi/build_role_metadata_sidecar.py`; `audit_role_metadata.py` invokes its CLI, and offline unit tests live at `experiments/aura-midi/tests/test_role_metadata_sidecar.py`.

The expected JSONL and summary are local generated artifacts, not committed training data:
- `experiments/aura-midi/runs/metadata-sidecar/role_metadata.jsonl`
- `experiments/aura-midi/runs/metadata-sidecar/role_metadata_summary.json`

**Status: IMPLEMENTED; HOSTED UNIT TESTS PASSED; LOCAL CORPUS RUN PENDING.** The GitHub Actions job passed all five offline unit tests and the CLI-help smoke check. The user's local workspace must still execute the builder against the actual corpus paths. Check source statuses, missing MIDI references, unknown splits, relative composition identity, and counts before treating the new sidecar as complete. A GitHub commit alone does not prove the local data scan succeeded.

The builder records source role labels separately from weak role candidates. In particular, GMD's raw rhythmic styles are preserved as source-style metadata rather than promoted to electronic subgenre labels; MAESTRO's Piano label is an instrument identity rather than a functional arrangement role; Slakh role candidates remain weak and versioned. Non-commercial datasets stay marked research-only, and attribution-only licenses remain provenance-pending.

### Immediate next step
Run tests and the sidecar builder locally, fix any concrete failures, then append the real execution output and per-source/split totals to the collaboration log and audit report. No new tokens, training, downloads, or checkpoint loads are authorized by this step.
