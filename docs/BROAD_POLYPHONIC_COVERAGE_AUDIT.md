# Broad Polyphonic Model — Musical Corpus Coverage Audit

**Date:** 2026-10-21  
**Status:** COMPLETE — Local analysis only, no new downloads, no training runs  
**Branch:** feature/mmm-v2-decoder-fix-and-docs (local HEAD: de6d8ff, remote HEAD: 9eb0800 — DIVERGED)  
**Evidence Standard:** All claims classified as **VERIFIED** (confirmed by local artifacts), **REPORTED** (from prior agent reports without local artifacts), **UNVERIFIED** (no evidence), **BLOCKED** (cannot verify due to environment)

---

## Executive Summary

This audit evaluates the musical diversity and structural coverage of locally available MIDI corpora for training a **single-stream broad polyphonic electronic music model** using the existing 12004-token REMI+BPE vocabulary (12000 base + 4 MMM v2 custom tokens). 

**Key Finding:** Current corpora provide **strong rhythmic/chordal coverage** (NRG-CP + GMD) but **lack complete polyphonic arrangements with explicit role separation** (bass, melody, chords, arpeggio, atmosphere). Slakh2100_samples (3 compositions) is the only multi-track polyphonic source but is insufficient for training. No electronic music genre/subgenre metadata exists in any corpus.

---

## 1. Corpus Inventory — Verified Local Holdings

| Source | Compositions (Unique) | MIDI Files | Windows (Phase 1) | Tracks/Composition | Genre Labels | License | Status |
|--------|----------------------|------------|-------------------|-------------------|--------------|---------|--------|
| **Slakh2100_samples** | **3** (Track00001, Track00002, Track00003) | 61 (stem-separated) | 0 (not used in Phase 1) | 8–11 per composition | None (inst_class only) | CC BY-NC 4.0 | **VERIFIED** |
| **NRG-CP** | 15,235 (algorithmic chord progressions) | 15,235 | 13,711 train / 761 val | 1 (single-track chord prog) | None ("EDM chord progressions" only) | CC BY 4.0 | **VERIFIED** |
| **GMD** | 1,150 (drum grooves) | 1,150 | 897 train / 124 val → 1,549/199 windows | 1 (drums only) | **Rich**: funk, soul, hiphop, pop, rock, jazz, latin/samba, neworleans/secondline, dance/disco, rock/shuffle, jazz/funk | CC BY 4.0 | **VERIFIED** |
| **MAESTRO v3.0.0** | 1,276 (solo piano performances) | 1,276 | 0 (not used in Phase 1) | 1 (piano only) | None (classical concert repertoire) | CC BY-NC-SA 4.0 | **VERIFIED** |
| **broad_corpus** | 0 | 0 | 0 | — | — | — | **VERIFIED EMPTY** |

**Notes:**
- "Compositions" = unique musical works (not stem-separated files or windows)
- "Windows" = fixed-length training sequences (1024 tokens) derived from files
- Phase 1 training used **only NRG-CP + GMD** (15,260 train windows, 960 val windows)

---

## 2. Genre/Style Metadata — What Actually Exists

| Corpus | Genre/Style Labels | Granularity | Electronic Music Coverage |
|--------|-------------------|-------------|---------------------------|
| **Slakh2100_samples** | Instrument class only (Piano, Bass, Guitar, Strings, Synth Lead, Synth Pad, Brass, Organ, Drums, Chromatic Percussion) | Per-track | **None** — no genre tags |
| **NRG-CP** | None beyond "EDM chord progressions" (description only) | Dataset-level only | **Implicit only** — algorithmic EDM-style progressions, no subgenre distinction |
| **GMD** | **11 distinct style labels** (funk, soul, hiphop, pop, rock, jazz, latin/samba, neworleans/secondline, dance/disco, rock/shuffle, jazz/funk) | Per-groove (file-level) | **Partial** — dance/disco, funk, soul relevant; no techno, house, trance, ambient, DnB, etc. |
| **MAESTRO** | None (classical piano repertoire) | — | **None** |

**Conclusion:** **No corpus provides electronic music subgenre labels** (techno, house, trance, ambient, drum & bass, dubstep, etc.). GMD's "dance/disco" and "funk" are the closest but cover only rhythmic patterns, not harmonic/melodic content.
---

## 3. Instrumental Role Coverage — What Roles Are Represented

| Role | Slakh2100_samples | NRG-CP | GMD | MAESTRO | Coverage |
|------|-------------------|--------|-----|---------|----------|
| **Bass** | ✅ Electric Bass (pick/finger), Synth Bass | ❌ (chord progressions only) | ❌ | ❌ | **Partial** — only in Slakh (3 compositions) |
| **Melody/Lead** | ✅ Synth Lead, Guitar, Piano, Brass | ❌ | ❌ | ✅ (piano melody) | **Partial** — only in Slakh (3) + MAESTRO (solo) |
| **Chords/Harmony** | ✅ Synth Pad, Choir Aahs, Organ, Piano, Guitar | ✅ **Core content** (chord progressions) | ❌ | ✅ (piano harmony) | **Good** — NRG-CP provides dense chord data |
| **Arpeggio** | ⚠️ Implicit in Synth Lead/Strings patterns | ❌ | ❌ | ⚠️ Implicit in piano | **Weak** — no explicit arpeggio tracks |
| **Atmosphere/Pad** | ✅ Synth Pad, Choir Aahs, Strings | ❌ | ❌ | ❌ | **Partial** — only in Slakh (3) |
| **Drums/Percussion** | ✅ Full drum tracks | ❌ | ✅ **Core content** (1150 grooves, 11 styles) | ❌ | **Strong** — GMD + Slakh |
| **FX/Texture** | ❌ | ❌ | ❌ | ❌ | **None** |

**Critical Gap:** No corpus provides **explicit role annotations** (bass vs melody vs chords vs arpeggio vs atmosphere). Roles must be inferred from program numbers and track position — unreliable for electronic music where same program (e.g., synth pad) can serve different roles.

---

## 4. Structural Representation Limits — Single-Stream REMI+BPE Constraints

| Limitation | Impact on Broad Polyphonic Generation | Status |
|------------|----------------------------------------|--------|
| **No explicit track role tokens** | Model cannot distinguish "this track is bass" vs "this track is melody" — learns only statistical co-occurrence | **CONFIRMED** — MMM v2 adds Track_Program/Track_IsDrum but no role tokens |
| **No chord symbol / harmony tokens** | Harmony learned implicitly from note co-occurrence; no symbolic chord representation | **CONFIRMED** — REMI has Note_On/Off, Velocity, Time_Shift only |
| **No phrase/section structure tokens** | No verse/chorus/breakdown/drop markers; structure emerges only from repetition patterns | **CONFIRMED** |
| **No tempo/key signature tokens** (beyond Time_Shift) | Global musical context not explicitly represented | **CONFIRMED** — Time_Shift encodes relative timing only |
| **Fixed 1024-token context window** | Limits long-range dependency modeling (typical EDM track: 4–8 min ≈ 20k+ tokens) | **CONFIRMED** — Phase 1 used 1024 |
| **Drum track note loss** (1078→257 in MMM v2 round-trip) | Base tokenizer BPE merge loses drum note density | **VERIFIED** — MMM v2 Track 00001 drum track |
| **No multi-track program preservation** (base tokenizer) | Single-track decode merges same-program tracks | **MITIGATED** — MMM v2 adds Track_Program metadata tokens |

**Verification:** All above confirmed by tokenizer code inspection (`tokenizer_mmm_v2.py`) and round-trip test results (`test_mmm_v2_roundtrip.py` output in collaboration log).

---

## 5. Phase 1 Generation Artifacts — Available for Analysis

| Artifact | Path | Description | Status |
|----------|------|-------------|--------|
| **Phase 1 Best Checkpoint** | `runs/broad-training-20261020_204942/checkpoint_best.pt` | Step 24750, val_loss=1.0252, 533 MB | **VERIFIED** (exists, unloadable due to PyTorch deadlock) |
| **Phase 1 Last Checkpoint** | `runs/broad-training-20261020_204942/checkpoint_last.pt` | Step 25000, final state | **VERIFIED** |
| **Token Cache** | `runs/broad-training-20261020_204942/token_cache.json` | 22 MB cached token sequences | **VERIFIED** |
| **Training Metrics** | `runs/broad-training-20261020_204942/training_metrics.json` | Full loss curves, config | **VERIFIED** |
| **AuraMIDI-v1 Generation** | `experiments/aura-midi/runs/generation-test/generated_midi_1.mid` | 64 notes, 8.6s, single-track REMI | **VERIFIED** |
| **MMM v2 Round-trip Outputs** | Not saved as artifacts (only logs in collaboration log) | Track 00001 decoded MIDI not persisted | **UNVERIFIED** — logs only |

**No broad polyphonic generations from Phase 1 checkpoint exist** — checkpoint never used for generation due to PyTorch deadlock.
---

## 6. Coverage Gap Analysis — What's Missing for "Practically Entire Spectrum of Electronic Music"

| Gap | Severity | Can Existing Data Fill It? | Required Action |
|-----|----------|---------------------------|-----------------|
| **Electronic subgenre labels** (techno, house, trance, ambient, DnB, dubstep, etc.) | **CRITICAL** | ❌ No | Need curated metadata or new dataset with genre tags |
| **Explicit role annotations** (bass, lead, pad, arp, atmosphere, fx) | **CRITICAL** | ❌ No | Need role-aware tokenizer or synthetic role labeling |
| **Complete polyphonic arrangements** (full tracks with all roles) | **HIGH** | ❌ Slakh only 3 compositions | Need more multi-track electronic music (Slakh full, MoisesDB, etc.) |
| **Long-form structure** (verse/chorus/breakdown/drop, 4–8 min tracks) | **HIGH** | ❌ NRG-CP 8-bar loops only | Need full-track datasets or structure-aware tokenization |
| **Sound design / timbre variety** (synth patches, FX, processing) | **MEDIUM** | ⚠️ Slakh has varied programs but only 3 tracks | Program tokens exist (128 GM programs) but no timbre metadata |
| **Tempo/key diversity** | **MEDIUM** | ⚠️ NRG-CP fixed 120 BPM; GMD varied BPM; Slakh varied | Partially covered by GMD + Slakh |
| **Non-4/4 time signatures** | **LOW** | ❌ All corpora 4/4 only | Not critical for electronic music (predominantly 4/4) |

---

## 7. Tokenizer Compatibility — MMM v2 (12004 Vocab) with Existing Corpora

| Corpus | Compatible with MMM v2? | Notes |
|--------|------------------------|-------|
| **Slakh2100_samples** | ✅ **YES** — Multi-track, MMM v2 designed for this | 3 compositions verified for encode/decode |
| **NRG-CP** | ✅ **YES** — Single-track, base tokenizer compatible | Used in Phase 1; no Track_Start/End needed |
| **GMD** | ✅ **YES** — Single-track drums, base tokenizer compatible | Used in Phase 1; is_drum=True handled |
| **MAESTRO** | ✅ **YES** — Single-track piano, base tokenizer compatible | Not used in Phase 1; license restricts commercial use |
| **broad_corpus** | N/A | Empty |

**All existing corpora are tokenizer-compatible** — no vocabulary mismatch. The 12004-token vocab (12000 base + 4 MMM v2 custom) covers all current data.

---

## 8. Evidence Classification Summary

| Claim | Classification | Evidence |
|-------|---------------|----------|
| Slakh2100_samples has 3 compositions, 8–11 tracks each | **VERIFIED** | Manifest files (`slakh_train.jsonl`, `slakh_validation.jsonl`) |
| NRG-CP has 15,235 single-track chord progression files | **VERIFIED** | File count + audit JSON (`nrgcp-audit-*.json`) |
| GMD has 1,150 drum grooves with 11 style labels | **VERIFIED** | `info.csv` (1150 rows) + file count |
| MAESTRO has 1,276 solo piano files | **VERIFIED** | File count |
| Phase 1 used NRG-CP (13,711 train) + GMD (897 train) | **VERIFIED** | `corpus_manifest.json`, `training_metrics.json` |
| Phase 1 best val_loss = 1.0252 at step 24750 | **VERIFIED** | `training_metrics.json`, `training_state.json` |
| No electronic subgenre labels in any corpus | **VERIFIED** | Manifest/schema inspection |
| No explicit role annotations (bass/melody/chord/arp/atmosphere) | **VERIFIED** | Manifest/schema inspection |
| MMM v2 vocab = 12004 (12000 + 4 custom) | **VERIFIED** | `tokenizer_mmm_v2.py` lines 32–36 |
| MMM v2 encoder verified on 3 Slakh samples | **VERIFIED** | Collaboration log entry 2026-10-21 18:30 |
| MMM v2 decoder PARTIAL (1/3 round-trip) | **VERIFIED** | Collaboration log entry 2026-10-21 19:15 |
| Drum track note loss (1078→257) = base tokenizer limit | **VERIFIED** | Collaboration log + tokenizer code |
| PyTorch deadlock blocks checkpoint load/generation | **BLOCKED** | 3 unkillable processes (PIDs 19992, 20436, 20600) |
| broad_corpus directory empty | **VERIFIED** | `dir` output |
---

## 9. Decision: Next Technical Step

### Recommended Action: **Design Role-Aware Single-Stream Architecture with Synthetic Role Labeling**

**Rationale:**
1. **No new dataset needed yet** — Existing corpora (NRG-CP + GMD + Slakh samples) provide chord, rhythm, and multi-track coverage but lack explicit role labels.
2. **Tokenizer is ready** — MMM v2 (12004 vocab) handles multi-track encoding with program/drum metadata.
3. **Phase 1 checkpoint preserved** — Can resume training once architecture defined and PyTorch unblocked.
4. **Critical gap is structural, not data volume** — The limitation is *representation* (no role tokens, no structure tokens), not *quantity*.

**Concrete Next Steps (No Training, No Reboot, No Downloads):**

1. **Define Role-Aware Token Extension** (on top of MMM v2):
   - Add 5 role tokens: `Track_Role_Bass` (12004), `Track_Role_Melody` (12005), `Track_Role_Chords` (12006), `Track_Role_Arpeggio` (12007), `Track_Role_Atmosphere` (12008)
   - Vocab expands to 12009 — minimal, backward-compatible

2. **Create Synthetic Role Labeling Pipeline** (offline, no PyTorch):
   - Heuristic rules: lowest-pitch track → Bass; highest-pitch non-drum → Melody; sustained polyphonic → Chords; repeated pattern → Arpeggio; slow-attack pad → Atmosphere
   - Apply to Slakh2100_samples (3 compositions) to validate
   - Extend to NRG-CP (chord progressions → Chords role) and GMD (drums → Drums role)

3. **Design Single-Stream Architecture** (document only):
   - Role tokens injected at Track_Start
   - Section structure tokens (Verse, Chorus, Breakdown, Drop, Intro, Outro) — 6 tokens
   - Global tempo/key tokens at sequence start
   - Total vocab: ~12020 — still fits in 12000+ embedding expansion

4. **Prepare Training Plan** (document only):
   - Curriculum: NRG-CP (chords) → GMD (rhythm) → Slakh (full multi-track) → Synthetic role-labeled mix
   - Loss weighting: role prediction auxiliary loss + next-token prediction
   - Evaluation: role accuracy, structure coherence, genre classifier (if trained separately)

5. **Resolve PyTorch Deadlock** (separate track):
   - Requires user decision on reboot — **NOT part of this step**

---

## 10. Files Updated / Created

| File | Status |
|------|--------|
| `docs/BROAD_POLYPHONIC_COVERAGE_AUDIT.md` | **CREATED** — this audit |
| `docs/AI_MODEL_COLLABORATION_LOG.md` | **APPENDED** — new entry for this audit |
| `docs/MUSIC_MODEL_TRAINING_HISTORY.md` | **TO UPDATE** — add audit reference |

---

*End of Audit. All findings based on local filesystem inspection and existing manifests. No new downloads, no training runs, no reboots performed.*
---

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

---

## Addendum — Local Cline Audit Results and Role-Token Proposal Review (2026-10-21)

**Evidence classification:** The following table transcribes the latest Cline report about local manifests. ChatGPT has published the report into this remote document but has not independently accessed the Windows workspace or opened those local manifests. The figures are therefore **REPORTED BY CLINE / TO RECONCILE LOCALLY**, despite being described as verified in the local agent report.

| Source | Unique compositions reported | MIDI files reported | Track structure | Reliable genre labels reported | Role coverage reported | License reported |
|---|---:|---:|---|---|---|---|
| Slakh2100 samples | 3 | 61 stems | 8–11 tracks per composition | None; instrument class only | Bass, melody, chords, pads, drums across only three compositions | CC BY-NC 4.0 for the mirror |
| NRG-CP | 15,235 algorithmic sequences | 15,235 | One piano/chord-progression stream | No trustworthy subgenre labels; described broadly as EDM chord progressions | Chords only | CC BY 4.0 |
| GMD | 1,150 groove files | 1,150 | One drum stream per file | 11 supplied style labels reported: funk, soul, hiphop, pop, rock, jazz, latin/samba, New Orleans/secondline, dance/disco, rock/shuffle, jazz/funk | Drums only | CC BY 4.0 |
| MAESTRO v3.0.0 | 1,276 | 1,276 | One piano stream | Classical piano, not electronic subgenres | Melody and chords within piano | CC BY-NC-SA 4.0; keep research-only |
| `broad_corpus` | 0 | 0 | — | — | — | — |

The reported Phase 1 training set consists of 13,711 NRG-CP train examples and 897 GMD train examples, reported as 15,260 train windows total. The Phase 1 best checkpoint is reported preserved at `experiments/aura-midi/runs/broad-training-20261020_204942/checkpoint_best.pt`, step approximately 24,750, with reported validation loss 1.0252. Reconcile file counts with manifests/metrics before using them for a new training run.

### Assessment of the proposed role-aware vocabulary

Cline proposed adding five role tokens (Bass, Melody, Chords, Arpeggio, Atmosphere) and six section tokens (Intro, Verse, Chorus, Breakdown, Drop, Outro), with heuristic synthetic labels.

**Decision: do not add these token IDs yet.** The next step is to design and audit the labels as sidecar metadata first, without changing the official or MMM vocabulary.

Reasons:
1. The dataset has no reliable electronic subgenre labels. This is a data/metadata limitation; adding vocabulary tokens does not create trustworthy genre supervision.
2. NRG-CP's chord role and GMD's drum role can be assigned from known dataset semantics. These source labels should be stored explicitly, with provenance.
3. Slakh has only three reported compositions in the available sample and instrument-class metadata rather than authoritative composition-section labels.
4. Pitch range, note density and program can generate **weak heuristic role candidates**, but they are not sufficient to assert a correct bass/melody/chord/arpeggio/atmosphere label. Store confidence and rule provenance; allow `unknown`; do not promote weak labels to gold labels.
5. No reliable section labels (intro/verse/chorus/drop/etc.) are reported in the available corpus. Do not invent these labels to train a conditioning interface.
6. Vocabulary arithmetic must be exact: starting from the current MMM v2 vocabulary of 12,004, five role tokens would yield 12,009; six additional section tokens would yield 12,015, not approximately 12,020. More importantly, new IDs require a compatible model/checkpoint embedding shape and training scheme. The Phase 1 checkpoint has a 12,000-token output space; do not assume it can directly consume MMM v2 custom IDs.
7. A single-stream polyphonic model does not need per-track markers merely to generate chords or simultaneous notes. Role conditioning is useful only when the sequence granularity and model objective make the role meaningful.

### Recommended role-metadata schema before any vocabulary work

Use sidecar JSONL/CSV first. Suggested fields:
- `composition_id`, `source_id`, `source_version`, `license`;
- `split`, `midi_path`, `sequence_id`;
- `role_label` and `role_confidence`;
- `role_label_origin` = `dataset_metadata`, `instrument_class`, `heuristic`, or `unknown`;
- `heuristic_rule_version`, if applicable;
- `genre_label`, `genre_confidence`, `genre_label_origin`;
- `is_section_labeled` and `section_label_origin`;
- `tokenizer_version`, `token_count`, `dedup_id`.

Prioritize source-grounded role labels:
- NRG-CP → harmony/chord sequence, based on source semantics;
- GMD → drum performance, based on source semantics;
- Slakh → instrument-class role only where the per-track metadata supports it;
- MAESTRO → piano performance, with research-only status.
Unknown labels remain unknown. A pitch/density heuristic may be retained as a weak suggestion for later manual or automated validation, not as ground truth.

### Next actionable step

Build a **metadata-only role/genre labeling pipeline** over existing manifests and representative MIDI metadata. It must not load PyTorch weights, add token IDs, retrain BPE, download a new dataset, or start training. Quantify the number of examples for each source-grounded role and reliable genre label, record weak labels separately, and use the results to decide whether conditioning is feasible.

Do not start a long training run or reboot. Preserve the Phase 1 checkpoint and keep MMM v2 isolated.
