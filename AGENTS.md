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
