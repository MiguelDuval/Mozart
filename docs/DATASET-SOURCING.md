# Mozart Dataset Sourcing Audit

## Purpose

This document records public dataset candidates for a commercially redistributable
Mozart training corpus. A candidate is **not** production-approved merely because
its repository or landing page displays an open-source or Creative Commons license.

The production gate requires source-level rights evidence, immutable revision,
file-level checksums, and an exact inventory/manifest match.

## Candidate A — WaivOps NRG-CP

**Status:** candidate for detailed rights audit; not yet approved.

- Source: https://github.com/patchbanks/WaivOps-NRG-CP
- DOI: https://doi.org/10.5281/zenodo.15304989
- Dataset type: MIDI
- Domain relevance: EDM chord progressions; dance, trance, house and related styles
- Size stated by publisher: 30,943 files
- Per-file structure: 8 bars
- Published license: CC BY 4.0
- Publisher rights statement: recordings are sourced from verified composers/providers
  for copyright clearance.
- Audit ledger: `docs/dataset-rights-audit-waivops-nrg-cp-v1.json`
- Current ledger status: **pending**. Public evidence establishes the Zenodo v1.0
  acquisition record, published CC BY 4.0 terms, and the publisher's copyright-clearance
  statement, but it does not by itself establish the missing authority, archive SHA-256,
  or exact MIDI inventory gates required by Mozart.
- Remaining audit: capture the exact dataset revision, download archive checksum,
  license text, attribution wording, and evidence linking the MIDI files to the
  entity authorized to license them.

Why it matters: this is directly aligned with Mozart's electronic/EDM target and
already matches the project's preferred 4–16 bar example range.

## Candidate B — PDMX

**Status:** candidate for a public-domain subset audit; not yet approved.

- Source: https://github.com/pnlong/PDMX
- Current Zenodo record: https://doi.org/10.5281/zenodo.15571083
- Dataset type: MusicXML with associated MIDI where conversion is available
- Published scope: over 250K public-domain scores
- Recommended subset: `no_license_conflict`
- Current record reports: 222,856 songs in that subset
- Important caveat: the authors report 31,221 songs (12.29%) with a mismatch between
  public-facing MuseScore copyright metadata and internal file copyright metadata.
- Additional caveat: some records do not have valid MIDI because conversion failed.
- Remaining audit: use only the recommended no-conflict subset, retain the original
  per-score license metadata, identify the exact MID file revision/archive checksum,
  and confirm that the distributed MIDI derivative is covered by the stated rights.

Why it matters: it can provide broad public-domain symbolic material beyond EDM while
keeping the rights filter explicit.

## Candidate C — GiantMIDI-Piano

**Status:** research-only candidate pending source-rights audit; not approved.

- Source: https://github.com/bytedance/GiantMIDI-Piano
- Dataset type: transcribed MIDI
- Published repository license: CC BY 4.0
- Published file count: 10,855 MIDI files
- Remaining audit: verify the scope of the CC BY grant against the underlying
  transcribed recordings and determine whether the dataset publisher had authority
  to license the full MIDI corpus for commercial training and redistribution.

Why it remains pending: an open license label on a repository is not by itself proof
that every underlying source right was cleared for redistribution.

## Rights-audit ledger

Before a candidate can become an `audited` or `release` manifest source, keep a
machine-validated ledger alongside the human-readable sourcing record. The ledger
must distinguish published license terms from the separate question of whether the
publisher had authority to grant those rights for the contained material.

`tools/validate_dataset_rights_audit.py` enforces this distinction for candidate
ledgers. An `approved` ledger is rejected unless every rights gate is verified, the
acquisition archive has a concrete SHA-256, and the exact MIDI inventory has a
concrete digest. A `pending` ledger may carry explicit blockers while research
continues.

## Release policy

Mozart should not place any of these candidates into the production manifest until:

1. the exact source revision is recorded;
2. the downloaded bytes have stable SHA-256 checksums;
3. commercial use and redistribution permissions are documented;
4. attribution obligations are recorded;
5. any upstream conflicts are excluded or independently cleared;
6. the discovered inventory exactly matches the audited manifest;
7. the resulting training corpus passes the deterministic MIDI/quality pipeline.

The first real corpus should remain separate from the repository until these gates are
complete. The example manifest in `docs/dataset-manifest.example.json` stays a template.
