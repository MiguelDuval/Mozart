# Broad Polyphonic Coverage Audit — Mozart

**Date:** 2026-10-21
**Status:** Preliminary evidence-only audit based on repository history and Cline reports; local ignored manifests, metrics, and MIDI files were not directly accessible during this audit. Counts marked reported must be reconciled with local artifacts before being treated as verified.

## Executive decision

Keep the Phase 1 checkpoint as the current single-stream research baseline. Do not start another long training run, do not download a large dataset yet, and do not let MMM v2 block the main model path.

The existing corpus is useful for chord progression and drum-pattern learning, but it does not yet demonstrate broad electronic-music coverage or high-quality polyphonic generation. The next useful action is an evidence-backed sample/evaluation set and a targeted assessment of missing musical roles.

Polyphony and multi-track output are distinct. Polyphony (overlapping notes/chords) can occur in one MIDI track. Multi-track modelling is needed only when the target use-case requires coordinated, separately recoverable instrument parts.

## 1. Dataset and role matrix

| Source | Reported available size | Role from current evidence | Genre evidence | License/status in project reports | Coverage conclusion |
|---|---:|---|---|---|---|
| NRG-CP | 15,235 unique files reported; 13,711 train / 761 validation / 763 test | Short algorithmic chord progressions / harmony | Reported house/progressive, trance/progressive and big-room labels; exact per-label counts unavailable in this audit | CC BY 4.0 reported; production-eligible pending provenance/manifest validation | Useful for chord transitions, weak evidence for full compositions, melody, bass and arrangement |
| GMD | 1,150 MIDI files reported; 897 train / 124 validation / 129 test | Drum/percussion patterns | Project report says labels are mainly rock/jazz/funk, not broad EDM subgenres | CC BY 4.0 reported; production-eligible pending provenance/manifest validation | Useful rhythm replay; insufficient alone for broad EDM genres or melodic roles |
| MAESTRO v3.0.0 | 1,276 MIDI files reported; 962 train / 137 validation / 177 test | Piano performance, melody/harmony practice | Classical piano, not electronic genre coverage | CC BY-NC-SA 4.0 reported; research-only and excluded from production-oriented corpus | Keep separate; does not address the largest electronic-genre gap |
| Slakh2100 Redux mirror | 3 compositions reported available at last check; larger download was in progress/rate-limited | Multi-instrument MIDI stems/arrangements, subject to round-trip preservation | Instrumentation is diverse, but broad target-EDM labels are not established | CC BY-NC 4.0 reported for this mirror; non-commercial research-only | Too small for training; useful for serializer testing only |
| E-GMD | 45,537 variants reported | Alternative drum-kit renderings of groove patterns | Same underlying groove patterns as GMD, not necessarily new genre coverage | CC BY 4.0 reported | Do not count variants as unique compositions; not a priority for the current gap |
| Official shikhr/music_maker base weights | Upstream data reported as about 11,000 piano MIDI files | Existing pretrained symbolic-MIDI prior | Piano-centered pretraining; composition-level genre coverage not established here | Model reported MIT; upstream training-data rights/provenance not fully established | Preserve as research baseline; do not infer production-cleared status from model license alone |

**Evidence rule:** counts and license details in this table are reported from existing project notes, not independently re-read local manifests or license files in the current environment. Reconcile values against existing manifests before assembling the next training dataset. Do not repeat the already completed 1,000-file tokenizer-validation pass solely to reconfirm encoding.

## 2. Coverage gaps

| Capability | Existing evidence | Assessment | Priority |
|---|---|---|---|
| Chord progressions | NRG-CP | Present in a narrow, short-pattern domain | Preserve without letting it dominate |
| Drum grooves | GMD | Present, with source labels not representative of the full electronic target | Preserve as replay; measure pattern diversity |
| Single-stream polyphony | Inherited MusicMaker BPE and Phase 1 training; generation claims need paired samples/evaluation | Not independently demonstrated at the desired musical quality | P0: evaluate first |
| Bass lines | No broad validated source identified in the available artifacts | Major gap | P1 |
| Synth leads / melodies | No broad EDM-specific source identified in available artifacts | Major gap | P1 |
| Arpeggios and evolving patterns | No source-level counts available | Unknown / likely gap | P1 |
| Pads and atmospheres | No source-level counts available | Unknown / likely gap | P2 |
| Genre diversity outside NRG-CP metadata | Reliable label counts unavailable | Major evidence gap | P0: quantify |
| Full-length phrase/section structure | NRG-CP is short algorithmic chord material; GMD is drum-pattern oriented | Not established | P2 |
| Multi-track reconstruction | MMM v2: one sample partly matched, one decode timed out, one decode not tested | Partial; drum-note loss is material | Optional research track |
| Genre conditioning | No validated conditioning path in available evidence | Not implemented/verified | Later, after reliable labels/data |

## 3. Phase 1 results require cautious interpretation

Cline reported the following for runs/broad-training-20261020_204942: checkpoint_best.pt, best validation loss 1.0252 around step 24,750, NRG-CP + GMD training, 14,608 MIDI files, 15,260 training windows, 960 validation windows, and peak VRAM 1.37 GB. These values are REPORTED, NOT independently verified in this audit. The training history notes earlier discrepancies in duration, validation count, and baseline loss.

Low token cross-entropy does not by itself establish improved musical quality. Before another fine-tune, create a reproducible evaluation pack using identical prompts, seeds, decoding settings, and MIDI validation for the baseline and Phase 1. Measure notes, duration, pitch range, polyphony/overlap, onset density, repetition, and source/genre metadata. Listening review is useful if a renderer is already available, but avoid adding large dependencies just for this step.

## 4. Recommended next actions

### P0 — Baseline generation/evaluation inventory
- Index existing generated MIDI files and their saved prompts/seeds/configurations from run directories.
- Where parsing works without PyTorch, measure notes, duration, track count, tempo, pitch range, note overlap, onset density, and simple repetition indicators.
- Mark missing settings/provenance UNVERIFIED.
- Do not label output musically good merely because it is long or structurally valid.

### P0 — Verify manifest and license facts
- Read existing corpus_manifest.json, data_manifest.json, dataset_info.json and saved metrics directly when local file access is available.
- Report unique compositions separately from windows, chunks and augmentation variants.
- Report explicit per-source genre counts only where authoritative metadata exists.
- Keep splits attached to original composition identity.

### P1 — Choose data based on a demonstrated gap
Only after populating source-level counts, select a representative source that addresses missing roles such as bass, synth melody and arpeggios. Check license, provenance, duplicates, tokenizer compatibility, archive size and free disk before full download. Separate research-only sources from production-oriented experiments.

### P1 — Keep MMM v2 optional
- Do not train for thousands of steps on the three currently reported Slakh compositions.
- Continue decoder fixes only if they do not trigger repeated PyTorch deadlock attempts.
- Track boundaries and drum-note preservation must be demonstrated before the tokenizer is called fully verified.
- Multi-track decoder work must not block the single-stream polyphonic model.

## 5. Current blockers and evidence labels

- Phase 1 checkpoint exists and is preserved: REPORTED by Cline; current filesystem accessibility was not independently checked in this audit.
- PyTorch checkpoint-load deadlock: REPORTED by Cline; current state of PIDs 19992, 20436 and 20600 must be rechecked before any conclusion.
- MMM v2 round-trip: PARTIAL, based on the latest Cline report.
- Slakh mirror sample count: three compositions reported; current download state UNVERIFIED.
- GitHub docs: this audit is on the feature branch for review and has not been merged into main.

## 6. Immediate next task

Use existing repository artifacts and saved metrics to populate per-source genre/role counts and index available single-stream MIDI samples. Do not restart Windows, do not start another long training run, and do not download a large dataset in this step.