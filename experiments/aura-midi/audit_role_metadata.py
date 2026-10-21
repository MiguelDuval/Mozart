#!/usr/bin/env python3
"""Compatibility entry point for the reproducible local role metadata audit.

The prior committed version stopped after defining MIDI-analysis helpers and had
no CLI/main routine, so it could not reproduce audit_report.json. The current
metadata-first workflow is implemented in build_role_metadata_sidecar.py.
"""
from build_role_metadata_sidecar import main


if __name__ == "__main__":
    raise SystemExit(main())
