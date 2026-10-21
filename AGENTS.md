# Agent Instructions — Mozart

Read this file before editing anything.

## Canonical documents

The project contract is defined by:

1. `docs/PROJECT_MASTER_PROMPT.md`
2. `docs/ARCHITECTURE.md`
3. `docs/ROADMAP.md`
4. `docs/TESTING.md`
5. `docs/DEPENDENCIES.md`
6. `docs/MIDI-CONTRACT.md`
7. `docs/LINK-TIMING.md`
8. `docs/AI-GENERATION.md`
9. `docs/MUSIC_MODEL_TRAINING_HISTORY.md` — **Long-term source of truth for all model training**
10. `docs/AI_MODEL_COLLABORATION_LOG.md` — **Permanent AI collaboration journal**

When documents conflict with source code or test evidence, investigate the discrepancy and update the documentation deliberately.

## Mandatory engineering rules

1. Keep `main` stable. Experimental work belongs on focused feature branches.
2. Read current source, callers, docs and recent commits before editing an existing subsystem.
3. After every meaningful change, run the smallest relevant tests and check GitHub Actions.
4. Do not claim success without actual build/test evidence.
5. Keep Android platform code, MIDI transport, timing, musical domain, generation, audio and UI boundaries separate.
6. The Android product UI is landscape-first and must remain usable horizontally.
7. Realtime threads must not perform avoidable blocking I/O, network requests, dynamic allocation, filesystem access or UI work.
8. MIDI transport code must not contain musical decision logic.
9. Musical generation must operate on semantic events, not raw platform MIDI bytes.
10. Ableton Link is a shared musical clock, not a master/slave transport. Mozart's first policy is to follow the session tempo/phase without continuously publishing tempo changes.
11. AI/network generation is never part of the realtime MIDI scheduling path.
12. Never store API keys, tokens or credentials in the repository.
13. Prefer deterministic algorithms with explicit seeds for tests.
14. Keep commits small and traceable.
15. Physical MIDI hardware remains the final authority for hardware-specific behavior.

## Project identity

Repository: `MiguelDuval/Mozart`

Product: personal Android MIDI instrument for accompaniment, rhythm/harmonic generation and synchronization.

Primary initial path:

**user/hardware input → musical intent → deterministic generator → Link-aligned scheduler → Android MIDI output**

## Reporting standard

At the end of meaningful work report:

- branch;
- exact commits;
- changed files/subsystems;
- build/test status;
- what is proven;
- what is not proven;
- next smallest step.

---

## Permanent AI Collaboration Protocol (Added 2026-10-21)

### Required Reading Before Significant Work
**Before any significant work, Cline MUST read:**
1. `docs/AI_MODEL_COLLABORATION_LOG.md` — latest entries and decisions
2. `docs/MUSIC_MODEL_TRAINING_HISTORY.md` — complete training history with evidence classification
3. `docs/MUSIC_MODEL_TRAINING_STRATEGY.md` — if available
4. `docs/PROJECT_MASTER_PROMPT.md`
5. `experiments/aura-midi/AURA_FINETUNE_READINESS.md` — if available in current checkout

### Git Hygiene
- Check `git status`, current branch, and `HEAD` before starting
- Verify upstream and remote
- Preserve uncommitted user changes
- Find existing commits and PRs related to the project
- **Known working branch:** `feature/link-clock` (but verify current branch first — do not switch blindly if it has needed uncommitted changes)
- No `reset`, `rebase`, `force-push`, or changes to `main`
- Work in small, meaningful changes
- Documents must not contain secrets, API keys, private tokens, or personal data

### Evidence Standards
- **Do not repeat completed experiments** without specific technical reason
- **Do not claim verification passed** without verifiable evidence
- After each substantial work phase, add entry to `docs/AI_MODEL_COLLABORATION_LOG.md` and update `docs/MUSIC_MODEL_TRAINING_HISTORY.md`
- All values and conclusions explicitly classified:
  - **VERIFIED** — confirmed by existing artifacts
  - **REPORTED, NOT VERIFIED** — from agent reports without artifacts
  - **UNVERIFIED** — no evidence available
  - **BLOCKED** — cannot be verified due to environment issues

### Reboot Prohibition
- **NO automatic computer reboots** — any reboot request requires explicit user permission
- No `Restart-Computer`, `shutdown /r`, `Stop-Computer`, or other reboot/shutdown commands
- No Scheduled Task creation that restarts computer
- No automatic reboot on PyTorch error or checkpoint load failure
- No repeated reboots as standard fix for process issues
- If reboot deemed absolutely necessary: save state, explain proven cause, stop for explicit user permission
- **For current task: reboot NOT permitted**

### Training Process Discipline
- Do not launch new training processes until previous process state verified
- Do not delete historical checkpoints, data, or user modifications
- Strategic model goal: **practically entire spectrum of electronic music**, not only dark melodic techno

### Documentation Maintenance
- Links to `docs/AI_MODEL_COLLABORATION_LOG.md` and `docs/MUSIC_MODEL_TRAINING_HISTORY.md` added to canonical documents list above
- These documents are the index and history — code, metrics, and training state remain in their respective project files
- After GitHub push: add commit SHA, branch, and document links to collaboration log

---

*This protocol is binding for all future Cline sessions on the Mozart project.*
