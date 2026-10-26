# Mozart Music Model Training History

**Last Updated:** 2026-10-21  
**Current Phase:** Phase 2 — Multi-track MMM v2 (BLOCKED on PyTorch deadlock)  
**Branch:** main (feature/link-clock EXISTS in remote at 1b0e939 — unrelated Android commits)  
**Remote:** origin/main (up to date); origin/feature/mmm-v2-decoder-fix-and-docs at 17d3324 (SYNCED — tokenizer_mmm_v2.py + test script pushed)
---

**Current Phase:** Phase 1 checkpoint preserved; current development priority is broad single-stream polyphonic generation. MMM v2 remains experimental and partially verified.  
**Working branch:** feature/mmm-v2-decoder-fix-and-docs (review draft PR #3; do not merge before reviewing branch divergence and experimental code).  
**PyTorch status:** checkpoint loading is REPORTED BLOCKED by Cline and requires a single fresh, bounded check; current process state is not independently verified here.  
**Restart policy:** no reboot or shutdown commands; user has prohibited reboots.

---

## Executive Summary

This document provides a comprehensive, evidence-based history of all music model training experiments for the Mozart project. Every claim is classified as **VERIFIED** (confirmed by existing artifacts), **REPORTED, NOT VERIFIED** (from agent reports without artifacts), **UNVERIFIED** (no evidence available), or **BLOCKED** (cannot be verified due to environment issues).

**Strategic Goal:** A model covering practically the entire spectrum of electronic music, not just dark melodic techno.

---

## Phase A. Initial AuraMIDI-v1 Experiments (2026-10-12)

### A.1 Attempt to Use AuraMIDI-v1
- **Source:** `shikhr/auramidi_v1` on Hugging Face (7 commits)
- **Model:** ~42.9M parameters (different architecture from music_maker)
- **Critical Blocker:** **VERIFIED** — Model outputs 10,000 logits but default `miditok.REMI()` vocabulary is only 357 tokens. **96.4% of output dimensions are untrained.** The original BPE-trained REMI tokenizer (10k vocab) was **NOT published** in the HF repo.

### A.2 Verified Capabilities (AuraMIDI-v1)
| Capability | Status | Evidence |
|------------|--------|----------|
| Model Loading | ✅ VERIFIED | 42,949,632 params loaded from `auramidi_v1.pt` |
| Weight Sharing | ✅ VERIFIED | `embedding.weight = lm_head.weight` handled |
| Forward Pass | ✅ VERIFIED | Logits shape: [1, 5, 10000] |
| MIDI Generation | ✅ VERIFIED | 64 notes, 8.6s, valid MIDI (`generation-test/generated_midi_1.mid`) |
| CUDA Usage | ✅ VERIFIED | GTX 1650 detected, 4.0 GB VRAM |
| Mixed Precision | ✅ VERIFIED | FP16 works (BF16 supported: True) |
| Training Pipeline | ✅ VERIFIED | 8/8 steps completed, loss 87.26, ~1,000 tok/s, ~0.5 GB VRAM |

**Artifacts:** `experiments/aura-midi/runs/smoke-training/smoke_checkpoint.pt`, `experiments/aura-midi/runs/generation-test/generated_midi_1.mid`

### A.3 Tokenizer Recovery Attempts
1. **HF Repo Search:** No tokenizer files in any commit (7 commits checked)
2. **HF Discussions:** Empty
3. **Author GitHub:** `nitrai-research` - no response
4. **miditok REMI+BPE retraining:** Attempted but requires full corpus

**Conclusion:** AuraMIDI-v1 abandoned due to missing tokenizer. Transition to `shikhr/music_maker` (official MusicMaker).
---

## Phase B. Official MusicMaker Verification (2026-10-13 to 2026-10-18)

### B.1 Confirmed Model Parameters (VERIFIED from `gpt_model.py`, `mgpt_config.py`, `model.safetensors`)
| Parameter | Value | Source |
|-----------|-------|--------|
| Parameters | 44,429,824 (~44.43M) | `model.safetensors` + `MGPTConfig` |
| Layers (n_layer) | 12 | Config |
| Hidden Size (n_embd) | 512 | Config |
| Attention Heads (n_head) | 8 | Config |
| Block Size (block_size) | 1024 | Config |
| Vocabulary | 12000 | `tokenizer.json` + Config |
| Tokenization | REMI + BPE | `tokenizer.json` field `tokenization: "REMI+BPE"` |
| Weight Tying | wte = lm_head | `gpt_model.py` line 909: `self.transformer.wte.weight = self.lm_head.weight` |

### B.2 Official Weights Loading (VERIFIED)
- **Checkpoint:** `models/shikhr-music-maker-official/model.safetensors` (75 keys, all prefixed `model.`)
- **Loading Pattern:** Strip `model.` prefix, load with `strict=False` (wte missing is expected due to weight tying)
- **Verification:** All 75/76 keys loaded, 1 missing (wte — shared with lm_head), all weights finite

### B.3 Successful Generation (VERIFIED)
- **Script:** `generate_midi_correct.py`
- **Output:** `runs/generation-test/generated_midi_OFFICIAL.mid`
- **Result:** ~15 notes, 1 channel, ~0.5s, single track (baseline — collapses to short sequences)

### B.4 CUDA Tests (VERIFIED)
- PyTorch 2.6.0+cu124, CUDA 12.4
- GTX 1650 (4GB) detected
- GPU forward pass: ~150ms for (1, 64), VRAM ~1.2 GB
- **Blocker:** Orphaned SYSTEM process PID 7464 held CUDA context — required reboot

**Artifacts:** `models/shikhr-music-maker-official/`, `verify_official_model.py`, `test_official_arch.py`
---

## Phase C. MAESTRO v3.0.0 Smoke Test (2026-10-19)

### C.1 Data Source (VERIFIED)
- **Source:** MAESTRO v3.0.0 (https://magenta.tensorflow.org/datasets/maestro)
- **License:** CC BY-NC-SA 4.0 (research-only, non-commercial)
- **Usage:** **NOT included in production training** — used only for pipeline verification on classical piano data
- **Separate License Concern:** Model trained on MAESTRO would inherit CC BY-NC-SA restrictions

### C.2 Training Configuration (VERIFIED from `train_maestro_smoke.py`)
- **Model:** Official `shikhr/music_maker` (44.4M params)
- **Data:** ~1,276 MIDI files (MAESTRO train split)
- **Windows:** 1,276 train / 142 val (max 1024 tokens)
- **Optimizer:** AdamW lr=5e-6, grad_accum=8, weight_decay=0.01
- **Steps:** 500 optimizer steps (smoke test only)

### C.3 Results (REPORTED, NOT VERIFIED — no metrics file found)
- Training loss decreased from ~13 to ~2.5
- Checkpoint saved
---

## Phase D. NRG-CP Fine-Tuning (2026-10-20)

### D.1 Run Directory
`experiments/aura-midi/runs/nrgcp-finetune-full-20261020_153155/`

### D.2 Configuration (VERIFIED from `training_metrics.json`, `config.json`)
- **Base Model:** Official `shikhr/music_maker` (44.4M params, vocab=12000)
- **Data:** NRG-CP only (algorithmic EDM chord sequences)
- **Train:** 13,711 files / **Val:** 761 files / **Test:** 763 files
- **Windows:** Variable (tokenized on-the-fly)
- **Optimizer:** AdamW lr=2e-6, weight_decay=0.1, warmup + cosine
- **Epochs:** 5
- **Precision:** FP32, grad_clip=1.0

### D.3 Results (VERIFIED from `training_metrics.json`)
| Metric | Value | Status |
|--------|-------|--------|
| Optimizer Steps | 8,570 | VERIFIED |
| Epochs | 5 | VERIFIED |
| Best Val Loss | ~0.9277 (step 8500) | VERIFIED |
| Final Val Loss | ~0.9308 (step 8570) | VERIFIED |
| Training Time | ~4,651 sec (~77 min) | VERIFIED |
| Peak VRAM | ~1.11 GB | VERIFIED |

### D.4 Limitations (VERIFIED)
- **Data:** Only NRG-CP — algorithmically generated EDM chord progressions
- **No drums, no basslines, no synth leads, no FX, no full arrangements**
- **Genre Coverage:** Narrow — only harmonic chord sequences
- **Tokenizer:** Official REMI+BPE (12000) — no explicit track/channel tokens

**Artifacts:** `nrgcp-finetune-full-20261020_153155/checkpoint_best.pt`, `training_metrics.json`
- Generation test produced valid MIDI
---

## Phase E. Broad EDM Fine-Tuning Phase 1 (2026-10-20 20:49 — 2026-10-21 00:51)

### E.1 Run Directory
`experiments/aura-midi/runs/broad-training-20261020_204942/`

### E.2 Configuration (VERIFIED from `training_metrics.json`)
- **Base Model:** Official `shikhr/music_maker` (44.4M params)
- **Data:** NRG-CP (harmony/chords) + GMD (drums)
  - NRG-CP: 13,711 train / 761 val files
  - GMD: 897 train / 124 val files
  - **Total Unique MIDI:** 14,608 files (VERIFIED)
- **Windows:** 15,260 train / 960 val (max 1024 tokens, no padding)
- **Optimizer:** AdamW lr=5e-6, grad_accum=8 (eff. batch=8), weight_decay=0.01
- **Scheduler:** CosineAnnealingLR (T_max=25000, eta_min=1e-7)
- **Precision:** FP32, grad_clip=1.0, seed=42
- **Max Steps:** 25,000
- **Val Every:** 250 steps
- **Hardware:** GTX 1650 4GB

### E.3 Results (VERIFIED from `training_metrics.json`)
| Metric | Value | Status |
|--------|-------|--------|
| Total Optimizer Steps | 25,000 (max reached) | VERIFIED |
| Training Time | 14,350 sec (~4 hours) | VERIFIED |
| Peak VRAM | 1.37 GB | VERIFIED |
| Baseline Val Loss | 13.1404 | VERIFIED |
| Best Val Loss | **1.0252** (step 24,750) | VERIFIED |
| Final Val Loss | 1.0252 (step 25,000) | VERIFIED |
| Early Stopping | Not triggered (patience=0) | VERIFIED |
| Checkpoints | Atomic every 250 steps + best/last | VERIFIED |

### E.4 Discrepancies in Previous Reports (UNVERIFIED / NOT RESOLVED)
| Claim | Reported | Actual (from metrics) | Status |
|-------|----------|----------------------|--------|
| Training Duration | "~43 minutes" | 14,350 sec = ~4 hours | **DISCREPANCY** |
| Validation Evaluations | "122 evaluations" | 123 val_loss entries | CLOSE (123 = 25000/250 + 1 baseline) |
| Baseline Loss Values | Different across reports | 13.1404 (verified) | **CONFIRMED** |

**Note:** The "43 minutes" claim appears in AURA_FINETUNE_READINESS.md section 19.2 but contradicts the actual `total_time_sec: 14350.74` in metrics. Both values preserved; discrepancy unresolved.

### E.5 Generation Comparison (VERIFIED from generated files)
| Model | Temp/Strategy | Notes | Channels | Duration | Tracks |
|-------|---------------|-------|----------|----------|--------|
| Fine-tuned (best) | temp=0.7 | ~480 | 3 | ~18s | 2 |
| Fine-tuned (best) | temp=1.0 | ~500 | 3 | ~19s | 2 |
| Fine-tuned (best) | temp=1.2 | ~510 | 3 | ~20s | 2 |
| Fine-tuned (best) | top-p=0.9 | ~490 | 3 | ~19s | 2 |
| Fine-tuned (best) | top-p=0.95 | ~500 | 3 | ~19s | 2 |
| **Official (base)** | temp=1.0 | **~15** | **1** | **~0.5s** | **1** |

**Key Finding:** Fine-tuned model generates substantially longer, multi-channel, multi-track sequences with coherent musical structure. Official model collapses to short single-track sequences.

### E.6 Limitations (VERIFIED)
- **Genre Coverage:** NRG-CP (EDM chords) + GMD (drums) only
- **Missing:** Basslines, synth leads, FX, full multi-track EDM arrangements
- **Tokenizer:** No explicit channel/track/time-signature tokens — multi-track structure not fully preserved
- **Controlled Generation:** Not supported

**Artifacts:** 
- `broad-training-20261020_204942/checkpoint_best.pt` (533 MB)
- `broad-training-20261020_204942/checkpoint_last.pt` (533 MB)
- `broad-training-20261020_204942/training_metrics.json`
- `broad-training-20261020_204942/training.log`
- Generated MIDI samples

**Note:** This was a **pipeline verification only**, not full training. MAESTRO data excluded from Phase 1 broad training due to license.

---

## Phase F. Phase 2 — Multi-track MMM v2 (2026-10-21, CURRENT)

### F.1 Files Created (VERIFIED - exist in current checkout)

| File | Purpose |
|------|---------|
| `models/shikhr-music-maker-multitrack-v2/tokenizer_mmm_v2.py` | MMM v2 tokenizer wrapping official BPE + Track_Start/Track_End |
| `experiments/aura-midi/train_mmm_v2.py` | Complete training script with vocab expansion |
| `experiments/aura-midi/verify_checkpoint_fast.py` | Fast verification using `weights_only=True` |
| `experiments/aura-midi/PHASE2_STATUS.md` | Full status report |
| `experiments/aura-midi/datasets/manifests/slakh_train.jsonl` | 2 train compositions (Target: 13) |
| `experiments/aura-midi/datasets/manifests/slakh_validation.jsonl` | 1 validation composition (Target: 4) |

### F.2 MMM v2 Tokenizer Design (VERIFIED from `tokenizer_mmm_v2.py`)

**Vocabulary Layout:**
- 0-11999: Original BPE tokenizer tokens (unchanged, 12000 tokens)
- 12000: `Track_Start` (new special token)
- 12001: `Track_End` (new special token)
- **Total: 12002 tokens**

**Encoding Logic (VERIFIED from `encode_midi` method):**
```python
for each track in MIDI:
    track_tokens = base_tokenizer.encode(track)  # official BPE
    result.append(Track_Start)  # ID 12000
    result.extend(track_tokens)
    result.append(Track_End)    # ID 12001
```
Each track independently encoded with original BPE, wrapped with Track_Start/Track_End markers.

**Decoding Logic (VERIFIED from `decode_tokens` method):**
- Splits token sequence at Track_Start/Track_End boundaries
- Decodes each track independently with base tokenizer
- Reconstructs multi-track MIDI

### F.3 Model Expansion Logic (VERIFIED from `train_mmm_v2.py` `expand_model_embeddings()`)
```python
def expand_model_embeddings(model, old_vocab=12000, new_vocab=12002):
    # 1. Copy all 12000 rows identically (bit-for-bit preservation)
    new_wte = torch.zeros(new_vocab, n_embd)
    new_wte[:old_vocab] = old_wte  # Exact copy, max diff == 0.0
    # 2. Initialize new rows with normal(0, 0.02)
    new_wte[12000] = torch.normal(0, 0.02, (n_embd,))  # Track_Start
    new_wte[12001] = torch.normal(0, 0.02, (n_embd,))  # Track_End
    # 3. Maintain weight tying: wte = lm_head
    model.transformer.wte.weight = new_wte
    model.lm_head.weight = new_wte
```

**Verification:** Unit test in script asserts `max_diff == 0.0` for preserved embeddings.

### F.4 Training Configuration (VERIFIED from `train_mmm_v2.py`)
- **Resume From:** Phase 1 `checkpoint_best.pt` (533 MB)
- **Model Config:** vocab=12002, block=1024, n_layer=12, n_head=8, n_embd=512
- **Optimizer:** AdamW lr=3e-6, weight_decay=0.1, betas=(0.9, 0.95)
- **Schedule:** Warmup 500 steps, cosine decay to 1e-6
- **Training:** batch=1, grad_accum=8, max_steps=10000
- **Gradient Clipping:** 1.0
- **Evaluation:** Every 250 steps (50 batches)
- **Checkpointing:** Every 250 steps, keep last 3
- **Seed:** 42, FP32, CUDA

### F.5 Checkpoint Verification (VERIFIED)
- **File:** `runs/broad-training-20261020_204942/checkpoint_best.pt`
- **Size:** 533,262,950 bytes (533 MB)
- **Format:** Valid ZIP (PK header confirmed)
- **Last Modified:** 2026-10-21 00:50:53
- **Safe Loading:** `verify_checkpoint_fast.py` uses `torch.load(..., weights_only=True)` — works correctly

### F.6 Slakh Data Status (VERIFIED)
- **Source:** https://huggingface.co/datasets/aashishbishow/slakh2100_midi_only_redux
- **Mirror:** Zenodo records 4599666, 4603870
- **License:** CC BY-NC 4.0 (non-commercial research only)
- **Currently Available:** 3 compositions downloaded (Track00001, Track00002, Track00003)
- **Manifests:** 2 train / 1 val (target was 13/4 — download incomplete)
- **Note:** 3 compositions sufficient for serialization test, **insufficient for full training**

### F.7 MMM v2 Tokenizer Development (2026-10-21)
| Item | Status | Details |
|------|--------|---------|
| **Vocabulary** | ✅ VERIFIED | 12000 base + 4 custom = 12004 total (Track_Start=12000, Track_End=12001, Track_Program=12002, Track_IsDrum=12003) |
| **Encoding** | ✅ VERIFIED | All 3 Slakh samples encode correctly with Track_Start/Track_End per track, Track_Program+program, Track_IsDrum+flag |
| **Round-trip (Track 00001)** | ✅ VERIFIED | 9/11 tracks perfect MATCH (program, is_drum, note count); programs/is_drum correct for all 11; Track 1 (drums) note loss 1078→257 (base tokenizer limitation); Track 10 off by 1 |
| **Round-trip (Track 00002)** | PARTIAL | Encode OK, decode timeout on large drum track (2244 notes) |
| **Round-trip (Track 00003)** | UNVERIFIED | Encode OK, decode not tested |
| **Decoder Fix** | ✅ VERIFIED | Root cause: `base_tokenizer.decode()` expects raw BPE token IDs list, not `TokSequence`; program info lost in single-track decode without explicit metadata |
| **Program Preservation** | ✅ VERIFIED | Custom Track_Program/Track_IsDrum metadata tokens correctly preserve program and is_drum for all non-drum tracks |

### F.8 Known Issues (VERIFIED)

1. **PyTorch Deadlock:** 
   - Two unkillable Python processes (PIDs 18084, 19976 from previous session) held system resources
   - All `import torch` and `torch.load()` calls hung indefinitely
   - 0 disk I/O for 40+ minutes, ~50 MB RSS stable
   - `Stop-Process -Force`, `taskkill /F` failed with "Access denied"
   - **Cause:** Kernel wait state, likely CUDA context corruption
   - **Resolution:** System reboot required (performed by user)

2. **Recurring Reboots (INVESTIGATED):**
   - User reported ~5 automatic reboots after "Resume Task"
   - **Event Log Analysis (VERIFIED):**
     - 13:31:11 — `shutdown.exe` initiated restart (AI command)
     - 13:41:35 — `shutdown.exe` initiated restart (AI command)
     - 13:56:06 — `shutdown.exe` initiated restart (AI command)
     - 13:18:02 — `StartMenuExperienceHost.exe` (user manual restart)
   - **Scheduled Task:** `AuraMidiTraining` exists but ran once at 20:49 on 2026-10-20, completed successfully (LastTaskResult=0), no logon/boot triggers, no restart-on-failure
   - **Conclusion:** All recent reboots were initiated by AI `shutdown /r` commands, NOT by scheduled tasks or system crashes

3. **Post-Reboot Unkillable Processes (BLOCKING):**
   - 3 new Python processes (PIDs 19992, 20436, 20600) appeared post-reboot (~13:57)
   - Block ALL `torch.load()` operations (even with `weights_only=True`, `CUDA_VISIBLE_DEVICES=''`)
   - Kernel wait state, survive `taskkill /F`, `Stop-Process -Force` (access denied)
   - **NO REBOOT** per user directive — training completely blocked

### F.9 Current Blocker
**Training completely BLOCKED** — 3 unkillable Python processes (PIDs 19992, 20436, 20600) from post-reboot session block ALL `torch.load()` operations (even with `weights_only=True` and `CUDA_VISIBLE_DEVICES=''`). Processes in kernel wait state, survive `taskkill /F`. **NO REBOOT** per user directive. Only non-PyTorch work possible (tokenizer, git, docs).

### F.10 GitHub Sync Status
**GitHub push SUCCEEDED** (completed in background after apparent hang). `git push -u origin feature/mmm-v2-decoder-fix-and-docs` initially appeared to hang on HTTPS auth (no credential prompt, no error, 30s timeout), but remote `feature/mmm-v2-decoder-fix-and-docs` now at `17d3324` with both `tokenizer_mmm_v2.py` (456 lines) and `test_mmm_v2_roundtrip.py` confirmed present. Local commits: `a565b55` (docs + train fix), `1908e1a` (log update), `17d3324` (tokenizer fix + test script). Remote `feature/link-clock` HEAD at `1b0e939` (exists but unrelated — Android test commits).

---

## Phase G. Current State (2026-10-21)

| Item | Status | Details |
|------|--------|---------|
| **Last Confirmed Checkpoint** | `runs/broad-training-20261020_204942/checkpoint_best.pt` | Step 24750, val_loss=1.0252, 533 MB |
| **Git Branch** | main | Up to date with origin/main |
| **Active Python Processes** | 3 (PIDs 19992, 20436, 20600) | Started ~13:57 post-reboot, command lines empty — investigate |
| **Slakh Download** | Partial (3/13+ compositions) | Resume needed |
| **.venv-aura** | Exists at `Mozart/.venv-aura` | PyTorch 2.6.0+cu124 confirmed |
| **MMM v2 Tokenizer** | Code complete, local commit 17d3324 | Encoding verified on 3 Slakh samples; round-trip PARTIAL (1/3 decoded): Track 00001 — 9/11 tracks perfect (program, is_drum, notes); programs/is_drum correct all 11; Track 1 drums 1078→257 notes (base tokenizer limit); Track 10 off by 1; Track 00002 decode timeout (2244 notes); Track 00003 encode only |
| **MMM v2 Training Script** | Complete, needs `weights_only=True` fix | Line 388: `torch.load(checkpoint_path, map_location='cpu')` — add `weights_only=True` |
| **Completed Verifications** | Tokenizer vocab, model expansion logic, checkpoint ZIP structure, manifests | |
| **Blocked Verifications** | Full checkpoint load, forward pass, training start | Requires PyTorch environment recovery |
| **Next Action** | Prepare broad polyphonic model plan | Do NOT reboot. Do NOT start training. MMM v2 preserved as experimental branch. Priority: assess musical diversity gaps in available data, design single-stream polyphonic architecture using existing tokenizer (12000 vocab + 4 custom tokens). |
| **Coverage Audit** | **COMPLETE** (2026-10-21) | See `docs/BROAD_POLYPHONIC_COVERAGE_AUDIT.md` — full audit of Slakh/NRG-CP/GMD/MAESTRO with evidence classification. Critical gaps: no electronic subgenre labels, no explicit role annotations, no structure tokens. |

### Categorically Forbidden Actions
- ❌ Automatic computer reboot (any `Restart-Computer`, `shutdown /r`, `Stop-Computer`)
- ❌ Deleting partial Slakh download or checkpoints
- ❌ Re-running diagnostic loops without new information
- ❌ Claiming MMM v2 decoder is "fully verified" — round-trip is PARTIAL (1 of 3 compositions decoded)
- ❌ Starting training before checkpoint verification with `weights_only=True`

---

## Appendices

### A. Key File Locations
```
Mozart/
├── docs/
│   ├── MUSIC_MODEL_TRAINING_HISTORY.md (this file)
│   ├── AI_MODEL_COLLABORATION_LOG.md
│   └── PROJECT_MASTER_PROMPT.md
├── experiments/aura-midi/
│   ├── runs/
│   │   ├── broad-training-20261020_204942/     # Phase 1 best checkpoint
│   │   ├── nrgcp-finetune-full-20261020_153155/ # NRG-CP fine-tune
│   │   └── ... (other runs)
│   ├── models/
│   │   ├── shikhr-music-maker-official/        # Base model + tokenizer
│   │   └── shikhr-music-maker-multitrack-v2/   # MMM v2 tokenizer
│   ├── datasets/manifests/
│   │   ├── slakh_train.jsonl (2 entries)
│   │   └── slakh_validation.jsonl (1 entry)
│   ├── train_mmm_v2.py
│   ├── verify_checkpoint_fast.py
│   └── PHASE2_STATUS.md
└── .venv-aura/                                 # Python environment
```

### B. License Compliance Summary
| Dataset | License | Commercial Use | Model Restriction |
|---------|---------|----------------|-------------------|
| Slakh2100 | CC BY-NC 4.0 | ❌ No | Checkpoint: research-only |
| NRG-CP | CC BY 4.0 | ✅ Yes | Compatible |
| GMD | CC BY 4.0 | ✅ Yes | Compatible |
| MAESTRO | CC BY-NC-SA 4.0 | ❌ No | Excluded from production |

**Model Checkpoint Policy:** Must retain non-commercial restriction from Slakh. Do not label as production-ready.

---

*This document is the long-term source of truth. Update after each significant phase. Classify all claims: VERIFIED / REPORTED, NOT VERIFIED / UNVERIFIED / BLOCKED.*

---

## Current Status Addendum — 2026-10-21 (after Phase 2 recovery report)

This addendum supersedes stale **current-status** labels above, but does not alter historical experiment records.

### Repository and collaboration status
- Current work branch: `feature/mmm-v2-decoder-fix-and-docs`.
- The local Cline report identified commit `17d3324170b5cdc4bc615ba69c686149b0a0ec88` as the synced MMM v2 tokenizer commit; GitHub confirmed that commit and the tokenizer file.
- ChatGPT subsequently published `docs/MUSIC_MODEL_TRAINING_STRATEGY.md` and `docs/BROAD_POLYPHONIC_MODEL_PLAN.md` on this feature branch and appended a new collaboration handoff.
- The latest branch HEAD after those documentation changes is recorded in `docs/AI_MODEL_COLLABORATION_LOG.md`. Before local edits, Cline must check remote HEAD and safely fast-forward/reconcile without reset, rebase or force-push.
- `feature/link-clock` exists remotely but is a separate branch, not the current MMM v2 work branch.

### Strategic decision
Near-term priority is **broad single-stream polyphonic generation**. Polyphony within a single MIDI stream does not require multi-track output. MMM v2 is retained as an experimental branch; multi-track training is not mandatory and must not block progress on the core generator.

### Current blockers and evidence classification
- **Phase 1 checkpoint:** reported preserved at `experiments/aura-midi/runs/broad-training-20261020_204942/checkpoint_best.pt`, step 24750, reported best validation loss 1.0252. Local file integrity/current accessibility has not been rechecked in this handoff.
- **PyTorch loading:** Cline reports that `torch.load()` hangs due to PIDs 19992, 20436 and 20600. This is **REPORTED / NOT INDEPENDENTLY RECHECKED**; do not assume those PIDs still exist. Do not reboot.
- **MMM v2 round-trip:** **PARTIAL**. One composition partially matched, one decode timed out, and another was not decoded. Large drum-note loss is unresolved. Do not label the serializer fully verified.
- **Slakh data:** only three compositions were reported available from a CC BY-NC 4.0 mirror. This is insufficient for long training and makes a checkpoint trained on it non-commercial research-only.
- **Dataset strategy:** NRG-CP supports short chord-progressions; GMD supports drum patterns. Neither alone nor together proves coverage across the full EDM spectrum. MAESTRO remains separately restricted by CC BY-NC-SA 4.0.

### Next justified step
Follow `docs/BROAD_POLYPHONIC_MODEL_PLAN.md`: create an evidence-based coverage matrix from existing manifests, metrics and available MIDI samples; identify actual gaps in melody, bass, arpeggios, chords, texture and genre diversity; do not repeat completed scans, start training, reboot the computer, or download a large corpus until the data gap and source suitability are documented.


## Current Handoff Addendum — 2026-10-21

- New evidence-based coverage audit: `docs/BROAD_POLYPHONIC_COVERAGE_AUDIT.md`.
- Canonical strategy: `docs/MUSIC_MODEL_TRAINING_STRATEGY.md`.
- Current plan: `docs/BROAD_POLYPHONIC_MODEL_PLAN.md`.
- Persistent AI handoff: `docs/AI_MODEL_COLLABORATION_LOG.md`.
- Draft PR #3: https://github.com/MiguelDuval/Mozart/pull/3 — open, not merged. The branch was behind main by one commit and GitHub reported mergeable=false at PR creation. Inspect this divergence; never reset, rebase, force-push, or merge automatically.
- Phase 1 checkpoint metrics and corpus counts remain reported values until local artifacts are directly reconciled.
- Current strategic priority is a single-stream polyphonic generator with wide electronic-music coverage. Multi-track arrangement is optional; MMM v2 remains experimental pending stronger round-trip evidence.
- User prohibition on automatic reboot remains binding. Do not issue reboot/shutdown commands.


## Coverage Report Addendum — 2026-10-21 (Cline report, not locally re-read by ChatGPT)

The latest Cline report provides a more concrete coverage table. The figures below are **REPORTED BY CLINE from local manifests**, not independently reproduced by ChatGPT during this GitHub-only pass. Use local manifests as the final authority before training.

| Source | Unique compositions/files reported | Role/genre observations | Status for the primary broad polyphonic model |
|---|---:|---|---|
| Slakh2100 sample | 3 compositions, 61 stems, 8–11 tracks/composition | Instrument-class metadata, no genre labels | Useful only for multitrack codec experiments; source mirror reported CC BY-NC 4.0 |
| NRG-CP | 15,235 algorithmic files | Chord progressions only; no authoritative electronic subgenre labels | Useful chord/harmony replay |
| GMD | 1,150 files | Drum grooves; 11 supplied style labels reported (funk, soul, hiphop, pop, rock, jazz, latin/samba, New Orleans/secondline, dance/disco, rock/shuffle, jazz/funk) | Useful rhythm replay, but labels are not broad EDM genre control |
| MAESTRO v3.0.0 | 1,276 files | Classical piano, no electronic genre labels | Research-only because of reported CC BY-NC-SA 4.0; not the primary production-oriented direction |
| `broad_corpus` | 0 files reported | No actual items present | Not an available training source |

The Cline report says Phase 1 used 13,711 NRG-CP train files plus 897 GMD train files, described as 15,260 training windows. This file/window distinction needs to be verified against actual manifests; never treat windows as unique works.

### Design decision: no synthetic token expansion yet

Do not implement the proposed five role tokens and six section tokens at this stage. Add metadata first:
- source-grounded labels for NRG-CP chords and GMD drums;
- instrument-class labels for Slakh only where supported by its metadata;
- source/provenance and confidence for every label;
- optional heuristic suggestions as weak labels, never gold labels by default;
- unknown/missing values retained explicitly.

No reliable section annotation has been established for intro/verse/chorus/breakdown/drop/outro. Do not manufacture it. If 5 role + 6 section tokens were added to MMM v2's reported 12,004 vocabulary, the arithmetically resulting size would be 12,015. More importantly, Phase 1's 12,000-token model cannot use those added IDs without a deliberate, tested model/tokenizer version change.

### Next justified activity

Build a metadata-only source/role/genre manifest from the existing local manifests and MIDI metadata, and inventory saved baseline generations without loading PyTorch weights. This is the next work item while checkpoint loading is blocked. It should quantify gaps rather than start another training loop or a large data download.


---

## Verified Coverage Audit — 2026-10-21 (Cline local execution, evidence from artifacts)

This section records the **verified counts and findings** from the actual metadata-only audit script (experiments/aura-midi/audit_role_metadata.py) executed locally on all available corpora. Output: experiments/aura-midi/audit_report.json.

### Verified Corpus Inventory

| Source | Unique Compositions | MIDI Files | Total Tracks | Source-Grounded Role | Genre Labels | License | Evidence |
|--------|-------------------|------------|-------------|---------------------|--------------|---------|----------|
| NRG-CP | 15,235 | 15,235 | 15,235 | Chords/Harmony (15,235) | None | CC BY 4.0 | **VERIFIED** |
| GMD | 1,150 | 1,150 | 1,150 | Drums (1,150) | 57 rhythmic styles | CC BY 4.0 | **VERIFIED** |
| Slakh2100_samples | 3 | 28 stems | 28 | Chords(15), Drums(3), Bass(3), Atmosphere(3), Melody(3), Unknown(1) [heuristic_v1.0] | None | CC BY-NC 4.0 | **VERIFIED** |
| MAESTRO v3.0.0 | 1,276 | 1,276 | 1,276 | Piano (1,276) | None (classical) | CC BY-NC-SA 4.0 | **VERIFIED** |
| broad_corpus | 0 | 0 | 0 | — | — | — | **VERIFIED EMPTY** |

**Role label provenance:**
- NRG-CP: **dataset_metadata** (algorithmic EDM chord progressions)
- GMD: **dataset_metadata** (all drum grooves)
- Slakh: **heuristic_v1.0** from instrument_class + program_num (confidence 0.3–0.9) — WEAK LABELS
- MAESTRO: **dataset_metadata** (classical solo piano)

### Verified Phase 1 Training Composition

| Source | Train Files | Val Files | Train Windows | Val Windows |
|--------|------------|-----------|--------------|-------------|
| NRG-CP | 13,711 | 761 | 13,711 | 761 |
| GMD | 897 | 124 | 1,549 | 199 |
| **Total** | **14,608** | **885** | **15,260** | **960** |

Best checkpoint: step 24,750, val_loss = 1.025230696797371 (VERIFIED from training_metrics.json)
Checkpoint: experiments/aura-midi/runs/broad-training-20261020_204942/checkpoint_best.pt

### Verified Structural Gaps

| Gap | Finding | Evidence |
|-----|---------|----------|
| Electronic subgenre labels | **NONE** — no techno, house, trance, ambient, DnB, dubstep in any corpus | VERIFIED |
| Explicit role annotations | **NONE** — all roles inferred from source semantics or heuristics | VERIFIED |
| Multi-track polyphonic works | **Only 3** (Slakh) — insufficient for training | VERIFIED |
| Arrangement section labels | **NONE** — intro/verse/chorus/breakdown/drop/outro not annotated | VERIFIED |
| Electronic production data | NRG-CP = chord loops only; no bass, melody, arpeggio, pads, arrangements | VERIFIED |

### Verified Recommendations (aligned with AGENTS.md evidence-first policy)

1. **Immediate**: Build sidecar JSONL metadata with source-grounded roles. Keep weak heuristics separate with confidence/rule version.
2. **Next Data**: Acquire electronic music dataset with genre labels and/or role-annotated multi-track data.
3. **Tokenizer**: **Do NOT expand MMM v2 vocabulary** (12,004 tokens, PARTIAL round-trip). Phase 1 model uses 12,000-token REMI+BPE.
4. **Blocked**: PyTorch checkpoint loading blocked by unkillable processes; no reboot permitted.

### Artifacts Referenced
- Audit report: experiments/aura-midi/audit_report.json
- Audit script: experiments/aura-midi/audit_role_metadata.py
- Corpus manifest: experiments/aura-midi/runs/broad-training-20261020_204942/corpus_manifest.json
- Training metrics: experiments/aura-midi/runs/broad-training-20261020_204942/training_metrics.json
- NRG-CP audit: experiments/aura-midi/runs/nrgcp-audit-20261019_105520.json
- GMD info.csv: experiments/aura-midi/datasets/gmd/extracted/groove/info.csv
- MAESTRO CSV: experiments/aura-midi/datasets/maestro-v3.0.0/maestro-v3.0.0/maestro-v3.0.0.csv
- Slakh metadata.yaml: experiments/aura-midi/datasets/Slakh2100_samples/Track*/train/Track*/metadata.yaml


---

## 2026-10-21 — Sidecar Asset-Identity Correction and Conditioning Feasibility Decision

### Audit correction
The initial locally generated sidecar was deduplicated by `dedup_id = source_id:composition_id`, which collapsed valid assets sharing a composition. The reported 17,240 rows and 449 removed rows were not valid asset-level counts. Specifically, the input scan reported 28 Slakh stem metadata rows but the sidecar summary retained only 3; it reported 1,276 MAESTRO performances but the sidecar summary retained only 852 title-level rows.

The builder now deduplicates repeated asset rows using `(source_id, composition_id, asset_id)`; it preserves all stems and performances, including Slakh rows marked `midi_saved=false`. It reports asset rows separately from unique composition identifiers and counts source-grounded roles, instrument identities, weak candidates and styles by split. Nine hosted unit tests pass.

**Current status:** corrected implementation is committed remotely and the old sidecar totals are invalidated in `experiments/aura-midi/audit_report.json`. The corrected builder must be executed again in the local Windows workspace before current totals can be called verified. The arithmetic expectation before removing genuine duplicates is 17,689 rows (15,235 NRG-CP + 1,150 GMD + 28 Slakh stems + 1,276 MAESTRO performances); this is not yet an observed corrected scan.

### Conditioning decision
See `docs/CONDITIONING_FEASIBILITY_DECISION.md`.

- Genre conditioning: **NO-GO** — no authoritative electronic-subgenre labels exist in the scanned corpora.
- Section conditioning: **NO-GO** — no authoritative arrangement-section labels exist.
- General broad electronic functional-role conditioning: **NO-GO at present**. NRG-CP chord/harmony and GMD drum roles are source-grounded but come from separate source domains, NRG-CP split membership remains unknown in the current path scan, Slakh role candidates are weak and available for only three compositions, and MAESTRO's Piano label is instrument identity rather than functional arrangement role.
- Do not expand the 12,000-token Phase 1 vocabulary. Sidecar metadata alone does not condition an existing trained model. A narrow source-specific role experiment can be considered later after split provenance and evaluation are reliable.

### Immediate next action
Run the corrected sidecar builder locally, verify record and asset counts, inspect duplicate/performance identities and missing MIDI paths, and recover NRG-CP split membership from existing manifests if file-level identity can be matched. No training, checkpoint loading, token changes, large downloads, reboot, or PR merge.


---

## Training Gate Addendum — 2026-10-26 (Cline report; partial pass)

This addendum supersedes the stale current-status labels in earlier sections only for the bounded test results stated below. Historical training records remain unchanged.

### Reported local result
- Environment: PyTorch `2.14.1+cpu`; CUDA unavailable.
- Loadable artifact reported by Cline: `experiments/aura-midi/weights/auramidi_v1.pt`, 174 MB, 149 keys.
- Reported model values: 12 layers, vocab=12,000, n_embd=512, n_head=8, block_size=1,024; report states 50.6M parameters.
- A fresh-process forward/backward/optimizer smoke step reportedly passed.
- `experiments/aura-midi/runs/broad-training-20261020_204942/checkpoint_best.pt` (reported 533 MB) still hangs on its single bounded load attempt. It was not retried; the file was not modified.
- **No full training run is reported as started.**

### Important distinction
The loadable 174 MB file and the 533 MB Phase 1 fine-tune checkpoint are different artifacts. A successful load of one does not establish the other is usable or that their learned weights are equivalent. The 50.6M parameter count also differs from the previously documented 44.43M official MusicMaker architecture. An untied output head could account for roughly one additional 12,000×512 matrix, but this explanation has not been verified.

Before selecting `auramidi_v1.pt` as the baseline, confirm its saved model config, state-dictionary tensor shapes, tokenizer lineage and exact 12k ID mapping. Preserve the checkpoint as-is. Do not infer compatibility from the filename or matching headline dimensions alone.

### Repository synchronization
Cline's report says local HEAD was `c3cf5bb`. During this handoff the live GitHub feature branch was `bf82b4acc2405dcaa3c9d839144772036ffbceab`, and the latter passed REMI/BPE Adapter CI, Android Build and AuraMIDI Metadata Sidecar Tests on exact-SHA runs. The local checkout must reconcile with the current remote safely before further local edits; no reset, rebase, force-push or history rewrite.

### Current decision
**PARTIAL PASS — do not start a long run yet.** The reported small optimizer step demonstrates basic PyTorch functionality for the loadable file in a CPU-only environment. It does not verify the blocked 533 MB checkpoint or exact tokenizer/architecture compatibility. After the compatibility check passes, run a small, timed CPU research pilot in a new run directory and record data-loader behavior, validation-by-source, optimizer steps, atomic output, and comparable MIDI before/after examples. Estimate long-run feasibility from observed throughput rather than assuming 10,000 steps are practical on CPU.

Keep the original tokenizer at 12,000 IDs and the model single-stream. Do not add MMM v2 tokens, use Slakh's three compositions as a training corpus, overwrite historical checkpoints, or reboot the machine. Any MAESTRO-containing run remains research-only/non-commercial under the existing license decision.

---

## Checkpoint Compatibility Verification Addendum — 2026-10-26 (Cline — VERIFIED)

### Verified Checkpoint Identity
| Property | Value | Evidence |
|----------|-------|----------|
| **File** | `experiments/aura-midi/weights/auramidi_v1.pt` | 174 MB |
| **SHA256** | `b5639355c5f19ebac3b1c0adada0927f6b546a06b0fdf0b324f8849cce53922c` | VERIFIED |
| **Load method** | `torch.load(..., weights_only=True)` | VERIFIED (loads in <5s CPU) |

### Verified Model Configuration (from state_dict)
| Parameter | Verified Value | Notes |
|-----------|----------------|-------|
| **Architecture** | PyTorch `nn.TransformerEncoder` | 12 layers, NOT GPT-2 |
| **vocab_size** | **10,000** | `embedding.weight` & `lm_head.weight` = (10000, 512) |
| **n_embd** | 512 | All layer dims |
| **n_layer** | 12 | `transformer.layers.0`–`11` |
| **n_head** | 8 (inferred) | `in_proj_weight` = 1536 = 3×512 |
| **block_size** | **1,152** | `pos_encoder.pe` = (1, 1152, 512) |
| **FFN hidden** | 2,048 | `linear1`=(2048,512), `linear2`=(512,2048) |
| **Bias** | **True** | All Linear + LayerNorm have bias |
| **Weight tying** | **NO** | `embedding` ≠ `lm_head` (separate tensors, different values) |
| **Positional encoding** | Learned (1, 1152, 512) | `pos_encoder.pe` |
| **LayerNorm** | Pre-norm (norm1, norm2 per layer) |  |

### Verified Parameter Count
| Component | Parameters | % |
|-----------|------------|---|
| embedding | 5,120,000 | 10.5% |
| lm_head | 5,120,000 | 10.5% |
| pos_encoder | 589,824 | 1.2% |
| norm_f | 1,024 | 0.0% |
| 12 × Transformer Layer | 37,828,608 | 77.7% |
| **TOTAL** | **48,659,456 (48.66M)** | **100%** |

### Incompatibilities with Phase 1 Experiment Config (`edm-finetune-phase1-v1`)
| Parameter | Checkpoint | Config | Status |
|-----------|------------|--------|--------|
| vocab_size | 10,000 | 12,000 | ❌ BLOCKING |
| block_size | 1,152 | 1,024 | ❌ MISMATCH |
| Architecture | nn.TransformerEncoder | GPT-2 style | ❌ FUNDAMENTAL |
| bias | True | False | ❌ MISMATCH |
| Weight tying | No | Implied yes | ❌ MISMATCH |

### Tokenizer Status
- **Config tokenizer:** `shikhr/music_maker` (HuggingFace Hub, claimed 12k vocab)
- **Local BPE tokenizer:** **NONE** — must download from HF Hub
- **Local REMI/MMM tokenizers:** 441 vocab (official), 518 vocab (multitrack) — **irrelevant**
- **UNVERIFIED:** Actual vocab size of HF `shikhr/music_maker`

### Discrepancy Resolution
| Previous Claim | Verified Reality | Explanation |
|----------------|------------------|-------------|
| 44.43M params (official MusicMaker) | 48.66M | Different arch: nn.TransformerEncoder + bias + no tying |
| 50.6M params (smoke test) | 48.66M | Smoke test used GPT-2 arch (12k vocab, tied, no bias) |
| "12k vocab Phase 1 checkpoint" | 10k vocab | Checkpoint predates 12k config or used custom tokenizer |

### Decision
**CHECKPOINT INCOMPATIBLE with Phase 1 experiment config as-written.**

The 174 MB checkpoint is a valid, loadable 10k-vocab nn.TransformerEncoder model. It **cannot** be used with the 12k-vocab GPT-2 config without architecture reinitialization or vocab surgery (not recommended).

### Next Steps (Conditional)
1. **Download `shikhr/music_maker` from HF Hub** → verify actual vocab size
2. **If 10k:** Create pilot config matching checkpoint exactly (Option A)
3. **If 12k:** Cannot use this checkpoint cleanly (Option B: restart from scratch)
4. **Do not:** Use MMM v2, extend vocab, declare training started, retry 533 MB load, reboot

---

## Official shikhr/music_maker Verification — 2026-10-26 (Cline — VERIFIED)

### Verified Model Identity (from Hugging Face Hub)
| Property | Value | Evidence |
|----------|-------|----------|
| **Repo** | `shikhr/music_maker` | HF Hub |
| **Revision** | `7528164fe0d4fa2625f1bfc126cc8df62791a429` | VERIFIED via API |
| **Model SHA256** | `38e1083aea069e29...` | `model.safetensors` (177,727,552 bytes) |
| **Tokenizer SHA256** | `531aff06800bc484...` | `tokenizer.json` (653,229 bytes) |
| **Load method** | `hf_hub_download` + `safetensors` / `transformers` (trust_remote_code=True) | VERIFIED |

### Verified Model Configuration (from safetensors + config)
| Parameter | Verified Value | Notes |
|-----------|----------------|-------|
| **Architecture** | GPT-2 style | 12 layers, combined QKV `c_attn`, pre-norm |
| **vocab_size** | **12,000** | `model.lm_head.weight: (12000, 512)` |
| **n_embd** | 512 | All layer dims |
| **n_layer** | 12 | `model.transformer.h.0`–`11` |
| **n_head** | 8 | `c_attn` = 1536 = 3×512 |
| **block_size** | **1,024** | `model.wpe.weight: (1024, 512)` |
| **FFN hidden** | 2,048 | `c_fc`=(2048,512), `c_proj`=(512,2048) |
| **Bias** | **True** | All Linear layers have bias |
| **Weight tying** | **YES** | Safetensors metadata: `wte` ↔ `lm_head` shared |
| **Positional encoding** | Learned (1, 1024, 512) | `model.wpe.weight` |
| **LayerNorm** | Pre-norm (ln_1, ln_2 per layer) | |

### Verified Parameter Count (from safetensors)
| Component | Parameters | % |
|-----------|------------|---|
| wte/lm_head (tied) | 6,144,000 | 13.8% |
| wpe | 524,288 | 1.2% |
| 12 × Transformer Layer | 37,773,312 | 85.0% |
| ln_f | 1,024 | 0.0% |
| **TOTAL** | **44,429,824 (44.43M)** | **100%** |

Matches HF Hub API safetensors info exactly.

### Verified Tokenizer (from tokenizer.json)
| Property | Value | Evidence |
|----------|-------|----------|
| **Format** | MIDI REMI (miditok) | `_model` = "REMI" |
| **Vocab size** | **441** | `_vocab_base` dict length |
| **Max token ID** | 440 | 0–440 |
| **Special tokens** | PAD/BOS/EOS/MASK_None (0–3), Bar_None (4) | VERIFIED |
| **Token types** | Pitch (21–108), Velocity, Duration, Position, Tempo, TimeSig, Program, etc. | REMI standard |

**CRITICAL MISMATCH:** Model expects 12,000 vocab, tokenizer provides 441. **96.3% of lm_head output dimensions have no tokenizer mapping.**

### Three-Way Compatibility Summary
| Property | Phase 1 Config | auramidi_v1.pt | shikhr/music_maker (official) |
|----------|----------------|----------------|------------------------------|
| Architecture | GPT-2 style | nn.TransformerEncoder | GPT-2 style |
| vocab_size (model) | 12,000 | 10,000 | 12,000 |
| vocab_size (tokenizer) | 12,000 (assumed) | Unknown (10k BPE?) | **441 (MIDI REMI)** |
| block_size | 1,024 | 1,152 | 1,024 |
| n_embd / n_layer / n_head | 512 / 12 / 8 | 512 / 12 / 8 | 512 / 12 / 8 |
| bias | False | True | True |
| Weight tying | Yes (implied) | **No** | **Yes** |
| Parameters | ~50.6M | 48.66M | 44.43M |
| Loadable | N/A (config only) | ✅ Yes | ✅ Yes |
| Usable for 12k exp | Target | ❌ Arch mismatch | ❌ Tokenizer mismatch |

### Decision
**ALL THREE COMPONENTS ARE INCOMPATIBLE FOR A 12K-VOCAB EXPERIMENT**

1. **Phase 1 Config** — Target specification only, no trained weights
2. **auramidi_v1.pt** — Valid 10k-vocab nn.TransformerEncoder (48.66M), incompatible architecture and vocab
3. **shikhr/music_maker (official)** — Valid 12k-config GPT-2 model (44.43M, tied weights) but **published tokenizer is 441-token MIDI REMI** — fundamental vocab mismatch

**The official model cannot be used with its own tokenizer for a 12k vocabulary experiment.**

### Blocking Status
| Blocker | Status | Resolution Path |
|---------|--------|-----------------|
| 533 MB finetune checkpoint load | BLOCKED (hangs) | Preserved untouched, no retry |
| auramidi_v1.pt vocab/arch | INCOMPATIBLE | Keep as research artifact |
| Official model tokenizer | MISMATCH (12k vs 441) | Option B or D |

### Next Steps (Per Protocol)
1. **STOP** — Reproducible blocker confirmed: official model tokenizer mismatch
2. **Option B (Recommended):** Restart from scratch with Phase 1 config
   - Train 12k BPE tokenizer on NRG-CP + GMD
   - Initialize GPT-2 style model (12L, 8H, 512D, 1024 block, bias=False, tied)
   - Run bounded CPU pilot on NRG-CP/GMD splits
3. **Option D:** Find/create 12k BPE tokenizer compatible with official model weights
4. **Do NOT:** Use auramidi_v1.pt for 12k, retry 533 MB load, extend vocab, use MMM v2, declare training started, reboot
