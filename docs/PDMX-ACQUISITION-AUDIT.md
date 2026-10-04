# PDMX acquisition audit

This audit is deliberately metadata-first. It does not copy PDMX dataset bytes into the
Mozart repository.

## Upstream contract

The audited target is Zenodo record 10.5281/zenodo.15571083, version v9. The record
publishes PDMX.csv, subset_paths.tar.gz, and mid.tar.gz together with their published
MD5 checksums.

The PDMX record defines:
- path as the MusicRender JSON path;
- mid as the associated MIDI path, which may be N/A;
- license and license_url as the original MuseScore licensing metadata;
- license_conflict as a disagreement between public-facing and internal MuseScore license data;
- subset:no_license_conflict as the recommended no-conflict subset;
- subset:all_valid as the subset with all associated MXL/PDF/MID files valid.

The public PDMX documentation says 31,221 songs (12.29%) have a public/internal license
metadata discrepancy and recommends the no_license_conflict subset. It reports 222,856
songs in that subset. It also says MIDI is unavailable for some corrupted source files.

## Reproducible local procedure

Use tools/audit_pdmx_source.py against the exact downloaded v9 artifacts:

~~~
python3 tools/audit_pdmx_source.py PDMX.csv subset_paths/no_license_conflict.txt \
  --midi-source mid.tar.gz \
  --output pdmx-audit-v9.json
~~~

The auditor:
1. streams PDMX.csv rather than loading the 225+ MB CSV into memory;
2. validates the required metadata/subset columns;
3. verifies the no_license_conflict subset file is exactly the same set as the CSV subset flag;
4. intersects that subset with rows having a concrete mid path;
5. audits the actual MIDI source as a directory or TAR/TAR.GZ;
6. rejects path traversal, duplicates, non-regular members, symlinks, and non-MIDI files;
7. computes per-file SHA-256 and a deterministic canonical inventory SHA-256;
8. reports exact missing/unexpected MIDI paths without committing the dataset itself.

## Legal interpretation

no_license_conflict is a publisher-defined metadata consistency filter. It is stronger
provenance evidence than an unqualified public-domain label, but it is not by itself a
contractual guarantee for commercial ML training or redistribution.

Accordingly, a successful technical audit must not change the production rights status to
approved. The authority-chain gate remains separate and still requires documentary
evidence of the underlying rights and coverage.
