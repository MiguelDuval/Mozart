# Broad Electronic-Music Coverage: Model Training Strategy

**Status:** Canonical product and training requirement for Mozart's symbolic-MIDI model experiments.  
**Scope:** Dataset selection, conditioning design, training plans, evaluation, checkpoint decisions, and future model releases.  
**Companion document:** [Project Master Prompt](PROJECT_MASTER_PROMPT.md)

## 1. Non-negotiable objective

Mozart's long-term symbolic-MIDI generator must cover **practically the full spectrum of electronic music**, as broadly and faithfully as lawful, representative training data makes possible. The goal is not a model specialized only for dark melodic techno.

Dark melodic techno remains one important style profile, not the overall training objective. A model or checkpoint trained on a narrow dataset must be labelled as a narrow-domain experiment; it must not be presented as the project's broad electronic-music model.

The intended product is a controllable generator that can create coherent material across many electronic styles, distinguish their musical characteristics, and support deliberate hybrid requests. “Broad coverage” is a measurable development objective, not a claim that every microgenre will be equally strong from the first release.

The model is symbolic MIDI, so coverage must include both complete musical roles and useful components: drums/percussion where represented, basslines, chords, arpeggios, leads, pads, riffs, rhythmic motifs, and multi-part patterns. A chord-progression-only dataset cannot establish full arrangement capability.

## 2. Intended stylistic coverage

Use a hierarchical, extensible, preferably multi-label taxonomy. These families are a coverage plan, not a claim that every family already has adequate licensed data.

| Family | Representative styles and variants |
|---|---|
| House | Deep house, soulful house, classic/garage house, disco/funky house, tech house, minimal/microhouse, acid house, progressive house |
| Techno | Detroit/classic, dub techno, minimal, hypnotic, dark, melodic, peak-time, acid, industrial, hard techno |
| Trance | Progressive trance, uplifting trance, vocal trance, Goa, psytrance, tech-trance |
| Drum & bass / jungle | Jungle, breakbeat-driven DnB, liquid, atmospheric, deep, rollers, jump-up, neurofunk |
| UK and broken-beat dance | UK garage, 2-step, speed garage, bassline, breakbeat, UK bass, breaks, big beat |
| Dubstep and bass music | UK dubstep, halftime, brostep, riddim, bass-heavy EDM, future bass, trap-influenced electronic styles |
| Electro and machine-funk | Electro, electro-funk, electro house, classic breaks, synth-driven club music |
| Mainstage / festival EDM | Big room, progressive EDM, hands-up and related festival-oriented dance styles |
| Hard dance | Hardstyle, hardcore, gabber, hard dance, industrial dance, hard techno, makina and related high-intensity forms |
| Downtempo and atmospheric | Ambient, chillout, downtempo, trip-hop, dub, atmospheric electronica |
| Experimental electronic music | IDM, glitch, abstract/broken rhythms, experimental electronica and hybrid forms |
| Retro and synthetic styles | Synthwave, darksynth, retrowave, chiptune and related synthesizer-led music |
| Global and cross-genre electronic dance | Afro house, amapiano, Afro-tech, baile funk, Latin club and other electronic hybrids, subject to suitable data and provenance |

Do not reduce these styles to tempo labels alone. Related genres can share BPM but differ in kick/bass relationship, swing, syncopation, phrasing, sound/role conventions, density, harmonic rhythm, and arrangement. Some styles overlap; the conditioning design must permit hybrid and multi-label requests rather than forcing every example into exactly one exclusive label.

The taxonomy should evolve when new licensed corpus sources or evaluation show a meaningful gap. Do not spend repeated cycles debating taxonomy while training and data work can proceed.

## 3. Conditioning requirements

Where the model architecture and available metadata support them, preserve explicit conditioning for:

- broad style family and subgenre, including multiple compatible labels;
- mood and energy;
- tempo or tempo range;
- key and scale where known;
- meter, subdivision, swing, syncopation, and rhythmic feel;
- musical role: drums, percussion, bass, chords, arpeggio, lead, pad, riff, or full/multi-part pattern;
- density, polyphony, pitch range, phrase length, and number of bars;
- optional instrumentation/track-role metadata.

Unknown metadata must be marked unknown, not invented. Keep the vocabulary runtime-neutral and versioned; do not silently change token ABI or conditioning semantics when adding labels.

A broad model should answer both genre-conditioned and hybrid-style requests. Training and evaluation should reveal whether requested style conditioning changes musical behavior, not merely whether a prompt token is accepted.

## 4. Corpus strategy and licensing

### 4.1 Build a broad, traceable corpus

Prefer a mixture of legally usable, musically representative MIDI sources over a huge but narrow corpus. Record for every source and imported collection:

- source name, canonical URL, version/revision, download date, and checksum;
- the exact applicable license and attribution requirements;
- whether commercial redistribution/use of resulting model weights is permitted or still requires review;
- source-level and file-level provenance where available;
- style-family/subgenre tags and confidence in those tags;
- track/instrument structure, role, tempo, meter, length, note density, and data-quality flags where available;
- exact and near-duplicate group IDs;
- the split/group assignment used for training, validation, and test.

A repository-level license label is not sufficient proof that every bundled MIDI file has compatible rights. Preserve the attribution and provenance information with the dataset manifest.

The production direction in the Project Master Prompt calls for project-owned weights with commercially usable rights. Therefore, do **not** promote a checkpoint to a production candidate until both the base weights and training-data rights have been cleared for the intended use. Non-commercial sources require explicit review and are excluded from production-eligible training by default.

### 4.2 Interpret current datasets honestly

- **NRG-CP** provides algorithmically generated, short EDM chord progressions. It is useful for testing chord-token prediction and narrow EDM harmony, but it is not a substitute for complete, diverse electronic MIDI arrangements.
- **MAESTRO** was used for a technical fine-tuning smoke test. Its classical-piano domain does not provide broad EDM coverage. Its CC BY-NC-SA terms make that derived smoke-test checkpoint ineligible for the project's commercially oriented production path unless an explicit rights review reaches a different conclusion.
- A low validation loss on one of these datasets proves neither broad genre coverage nor professional musical quality.

Retain existing experiments as evidence about infrastructure. Do not use their results to overstate the final model's capabilities.

## 5. Dataset quality, deduplication, and splits

Before a substantial training run:

1. Build one reproducible manifest over the available, rights-reviewed corpus.
2. Deduplicate exact files and exact token sequences; where practical, detect near-duplicates and alternate exports of the same composition.
3. Group related versions of a track/composition and, where metadata permits, artist/source groups before splitting.
4. Make deterministic train/validation/test splits and record the seed and manifest hashes.
5. Prevent exact duplicates and related versions from leaking across splits.
6. Report total and per-family counts before and after filtering.
7. Diagnose missing or underrepresented families instead of allowing the largest source to silently define “electronic music.”

Do not repeatedly re-tokenize files that have already passed validation. Use versioned, checksummed caches tied to the exact tokenizer/configuration and source manifest. Rebuild a cache only when its source, tokenizer, or schema changes.

## 6. Long-term training plan

### Stage A — finish evaluating the current narrow-domain run

The reported NRG-CP run completed five epochs and 8,570 optimizer steps, with reported best validation loss 0.9277 and final loss 0.9308. Treat this as an NRG-CP adaptation candidate only until a controlled, like-for-like baseline evaluation and qualitative generation review have been completed.

Do not restart or repeat the completed tokenizer/CUDA checks. Evaluate the existing artifacts and checkpoint first.

### Stage B — assemble the broad, rights-reviewed corpus

Use the corpus inventory to identify coverage gaps and collect representative, diverse files under compatible terms. Prefer content that captures whole phrases and separate musical roles, not only isolated chord grids. Preserve genre and provenance metadata throughout preprocessing.

### Stage C — broad-domain training

Train a broad electronic-music foundation/adaptation checkpoint on the balanced mixture, using the complete eligible training set rather than the first few files. Retain the original architecture/tokenizer compatibility unless measured evidence justifies a separately evaluated architecture change.

Sample across style families intentionally. Pure token-count weighting can let the largest corpus dominate and erase minority styles; use and document a defensible family/source sampling policy. The goal is useful macro-level performance across styles, not only the best overall average on the dominant family.

### Stage D — protect coverage during adaptation

Use checkpoints and validation to identify overfitting and catastrophic forgetting. If specialized adaptation is useful, keep the broad model as the anchor and interleave representative data from other families or use a separately identified adapter/checkpoint. Never replace the broad candidate with a narrow fine-tune without evaluating its effect on the other families.

Specialist models or adapters may be added later when evidence shows a real benefit, but a collection of narrow experiments does not itself satisfy the broad-model objective.

### Stage E — extend and maintain

Longer training is acceptable when supported by diverse, appropriately licensed data and stable validation. Use reproducible configs, periodic atomic checkpoints, resume support, finite-loss/gradient checks, and a clear stopping rule. Avoid fixed arbitrary tiny runs that merely prove the loop executes, but also avoid continuing once validation and qualitative checks show no useful progress.

## 7. Evaluation standard

Evaluate both global and per-family behavior. Do not let one aggregate token-weighted loss hide weak or absent coverage for smaller styles.

Minimum evaluation dimensions:

- consistent token-weighted cross-entropy and perplexity on held-out data;
- per-family and macro-averaged metrics, with counts of files/sequences/tokens;
- correct checkpoint reload and tokenizer/config compatibility;
- valid MIDI outputs with non-empty notes, positive duration, valid event structure, and no obvious token/note collapse;
- generation under identical prompts, seeds, and settings for model comparisons;
- style-conditioned samples for multiple families and hybrid prompts;
- pitch, note density, onset, repetition, duration, track/role, and other available structural statistics;
- listening-based A/B review of rendered samples when a local renderer is available, with the method and limits stated clearly.

The held-out test set must not guide optimizer updates, checkpoint selection, or hyperparameter tuning. Use it for final evaluation after choices are fixed.

Lower loss indicates better next-token prediction under that evaluation protocol; it does not by itself prove that generated music sounds better, that a requested style is recognizable, or that all electronic genres are covered.

## 8. Release gate

A checkpoint is not the broad production model until all of the following are demonstrated:

- provenance and rights for base weights, tokenizer, training data, and transformations have been reviewed;
- the dataset represents the intended breadth, and actual family coverage is documented;
- controlled held-out metrics and generation samples exist for multiple style families;
- style-conditioning behavior and obvious failures are documented;
- checkpoint loading, inference, and MIDI validation are reproducible;
- model version, tokenizer version, conditioning vocabulary, data manifest, training configuration, and evaluation report are linked by a release manifest.

If coverage is incomplete, state exactly which families are supported, weak, untested, or absent. Do not market a narrow-domain checkpoint as universal.

## 9. Agent operating rule

This document is the standing strategic requirement. Once a prerequisite has passed, do not re-open it without new contradictory evidence. Prefer sustained dataset preparation and training work with checkpoints and automated monitoring over repeated audit-only cycles.

Every material result must distinguish:
- **infrastructure success** (the code runs);
- **dataset-fit evidence** (held-out prediction and structural tests);
- **musical evidence** (style-appropriate generated MIDI and, where possible, listening);
- **release readiness** (rights, provenance, reproducibility, and integration).

The objective is a broad electronic-music generator. Dark melodic techno is one destination among many, not the boundary of the project.
