# Music Model Training Strategy — Mozart

**Status:** Canonical strategic guidance for symbolic-MIDI model work.  
**Last updated:** 2026-10-21  
**Scope:** Research and development of a broadly capable electronic-music generator.

## 1. Permanent goal

Build a controllable symbolic music model that can generate musically useful material across practically the full spectrum of electronic music—not only dark melodic techno, piano chords, or drum patterns.

Target families include house, techno, trance, drum & bass/jungle, UK garage/breaks, dubstep and bass music, electro, festival EDM, hard dance, ambient/downtempo, IDM/experimental electronics, synthwave/chiptune, and electronic-hybrid styles. This is a coverage goal, not a claim that the current corpus already represents all these families.

**Genre breadth and MIDI track count are separate dimensions.** A single MIDI track can contain polyphony. Multi-track arrangement generation is valuable for complete coordinated arrangements, but is not a prerequisite for every model-training stage.

## 2. Near-term modelling priority

Prioritize a reliable **single-stream polyphonic symbolic generator** using the already trained Phase 1 checkpoint and the original compatible tokenizer, unless evidence shows a specific limitation that blocks the desired musical behavior.

The next development stages should be:

1. Establish the quality and failure modes of Phase 1 generation using actual MIDI samples and reproducible evaluation.
2. Audit gaps in harmonic, melodic, rhythmic, bass, arpeggio, texture, and stylistic coverage.
3. Add genuinely diverse, appropriately licensed data that addresses identified gaps.
4. Fine-tune conservatively with replay from existing sources to reduce catastrophic forgetting.
5. Add genre/role conditioning only when reliable metadata and an explicit, tested conditioning path exist.
6. Revisit multi-track serialization and arrangement modelling when there is a demonstrated product need and sufficient real multi-track data.

Do not repeat the same long fine-tuning run on an unchanged corpus merely to accumulate steps.

## 3. Model and tokenizer preservation

Phase 1 checkpoint:
`experiments/aura-midi/runs/broad-training-20261020_204942/checkpoint_best.pt`

Original `shikhr/music_maker` model/tokenizer:
`experiments/aura-midi/models/shikhr-music-maker-official/`

Previously reported Phase 1 configuration: about 44.43M parameters, 12 layers, width 512, 8 attention heads, context 1024, and 12,000-token REMI+BPE vocabulary. The reported best validation loss was 1.0252; use the run artifacts to confirm any figures before treating them as independently verified.

Preserve the official BPE token IDs and Phase 1 checkpoint. Never replace the learned BPE vocabulary with the 441-token base REMI vocabulary while retaining the original model weights. A token ID is meaningful only with the exact tokenizer mapping used to train the embedding row.

MMM v2, including IDs 12000–12003 and track/program/drum markers, is an isolated experimental representation. Its round-trip status is **PARTIAL**, not fully verified. Do not make MMM v2 the default route for single-stream generation or long training unless the experiment proves that it is needed.

## 4. Data strategy

Build a source manifest that records, at minimum:
- dataset and version;
- source URL and retrieval date;
- license and use restrictions;
- identity of the original composition;
- train/validation/test split;
- deduplication identity;
- reliable genre metadata (or `unknown`);
- musical roles/instruments where available;
- tokenizer/config version and tokenization status.

Distinguish **research-eligible** data from **production-eligible** data. License of the newest dataset alone is not sufficient to establish that a model checkpoint is production-eligible; upstream pretrained weights and earlier training data also matter.

Known sources and current role:
- **NRG-CP:** useful for short EDM chord-progressions; not a complete EDM corpus. Reported license: CC BY 4.0.
- **GMD:** useful for drum/percussion performance patterns; it does not supply bass, synth leads, full arrangements, or broad EDM coverage by itself. Reported license: CC BY 4.0.
- **MAESTRO:** primarily classical piano; CC BY-NC-SA 4.0. Keep separate from production-oriented training unless its use and resulting model status have been explicitly assessed.
- **Slakh2100 mirror currently used:** reported CC BY-NC 4.0. Treat models trained on this material as non-commercial research candidates. Partial download and small sample count are not enough for long training.

Do not download very large datasets until there is a documented diversity gap that they address, compatibility and license have been checked, and disk requirements are acceptable. Prefer small, representative sample audits before full downloads. Do not inflate counts using duplicates or repeated files.

## 5. Training safeguards

- Keep train, validation, and test sets separated by composition or deduplicated identity, not only by derived windows.
- Do not concatenate the end of one MIDI composition with the start of another.
- Train autoregressively with correctly shifted input and target tokens.
- Do not count padding tokens as real musical targets.
- Compute validation cross-entropy consistently, preferably weighted by target-token count.
- Report aggregate metrics and per-source/per-genre metrics when supported by enough data.
- Preserve replay from previous sources when adding new sources, and check for source-specific regression.
- Save best and last checkpoints atomically, including optimizer/scheduler and RNG state when resumability is required.
- Never report training as started or complete without real optimizer-step and artifact evidence.
- Do not infer music quality from loss alone; preserve generated MIDI samples and inspect them independently.

## 6. Conditioning and musical roles

A mixed corpus does not, by itself, give reliable genre control. Prefer authoritative source metadata; otherwise mark genre as `unknown` rather than guessing from BPM or filenames.

A later conditioning system may support genre, tempo range, key/scale, musical role, density, energy, and arrangement intent. Implement only conditions that can be represented and evaluated. Do not add token IDs or change model shapes without explicit versioning and preservation of pretrained mappings.

Single-stream polyphonic generation and multi-track arrangement generation should have separate acceptance criteria. An acceptable single-stream model can generate multiple simultaneous notes in one track. A multi-track model must additionally prove track-level round-trip, correct instrument/program metadata, event timing, and preservation of independent same-program tracks.

## 7. Current blockers and operational rules

As of the latest Cline report:
- Phase 1 checkpoint is reported preserved.
- MMM v2 round-trip is partial: one sample partly matched, another timed out, and one was not decoded.
- PyTorch checkpoint-loading is reported blocked by three unkillable Python processes; this diagnosis is from Cline's report and should be rechecked if the environment changes.
- The user has prohibited reboots. This prohibition is binding: never issue reboot/shutdown commands or create a task that does so.
- Continue independent work (documentation, source metadata, manifest analysis, dedup planning, tokenization/decoder work that does not require loading model weights) while PyTorch loading is blocked.
- Do not start a long training run until the active processes, model-loading path, tokenizer mapping, and relevant data split are in a usable state. Do not turn this into repeated identical diagnostics.

## 8. Definition of progress

Meaningful progress means one of:
- actual validated single-stream polyphonic MIDI samples with reproducible settings;
- an evidence-backed data-diversity audit that identifies a specific gap;
- a suitable new data source acquired and represented in a reproducible manifest;
- an actual training run with correct data, checkpoints, and comparable evaluation;
- a validated improvement to generation/conditioning or a clearly established technical limitation.

More scripts, larger dataset counts, lower training loss, or repeated checkpoint-loading attempts are not, by themselves, sufficient evidence of improved musical capability.
