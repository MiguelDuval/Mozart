# Mozart Music Model Training History

**Last Updated:** 2026-10-21  
**Current Phase:** Phase 2 — Multi-track MMM v2 (BLOCKED on PyTorch deadlock)  
**Branch:** main (feature/link-clock does not exist)  
**Remote:** origin/main (up to date)

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

### F.7 Known Issues (VERIFIED)

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

3. **MMM v2 Track Serialization (UNVERIFIED — CRITICAL):**
   - **Contradiction in PHASE2_STATUS.md:** Claims "9 tracks preserved" but also "entire composition serialized as one track with markers at boundaries"
   - **Current Implementation:** `encode_midi` iterates tracks and wraps EACH with Track_Start/Track_End — **this IS correct per-track encoding**
   - **Round-trip Test:** Only tested on 1 Slakh sample (Track00003, 9 tracks) — track count preserved in that test
   - **Not Yet Tested:** Compositions with same program on multiple tracks (previously caused merging)
   - **Status:** UNVERIFIED until comprehensive round-trip on multiple compositions

### F.8 Current Blocker
**PyTorch environment deadlocked by unkillable processes (now cleared by reboot).** 
Training script `train_mmm_v2.py` has not yet been executed successfully in current session.

---

## Phase G. Current State (2026-10-21)

| Item | Status | Details |
|------|--------|---------|
| **Last Confirmed Checkpoint** | `runs/broad-training-20261020_204942/checkpoint_best.pt` | Step 24750, val_loss=1.0252, 533 MB |
| **Git Branch** | main | Up to date with origin/main |
| **Active Python Processes** | 3 (PIDs 19992, 20436, 20600) | Started ~13:57 post-reboot, command lines empty — investigate |
| **Slakh Download** | Partial (3/13+ compositions) | Resume needed |
| **.venv-aura** | Exists at `Mozart/.venv-aura` | PyTorch 2.6.0+cu124 confirmed |
| **MMM v2 Tokenizer** | Code complete, tested on 1 sample | Round-trip track count verified on 1 composition |
| **MMM v2 Training Script** | Complete, needs `weights_only=True` fix | Line 388: `torch.load(checkpoint_path, map_location='cpu')` — add `weights_only=True` |
| **Completed Verifications** | Tokenizer vocab, model expansion logic, checkpoint ZIP structure, manifests | |
| **Blocked Verifications** | Full checkpoint load, forward pass, training start | Requires PyTorch environment recovery |
| **Next Action** | Fix `train_mmm_v2.py` loading, verify checkpoint, start training | Do NOT reboot |

### Categorically Forbidden Actions
- ❌ Automatic computer reboot (any `Restart-Computer`, `shutdown /r`, `Stop-Computer`)
- ❌ Deleting partial Slakh download or checkpoints
- ❌ Re-running diagnostic loops without new information
- ❌ Claiming MMM v2 is "multi-track" without verified round-trip on multiple compositions
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
