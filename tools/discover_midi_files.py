#!/usr/bin/env python3
"""Discover MIDI files deterministically and emit a checksum inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


MIDI_SUFFIXES = {".mid", ".midi"}


def discover(root: Path) -> list[dict]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"dataset root is not a directory: {root}")

    entries: list[dict] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file() or path.suffix.casefold() not in MIDI_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        entries.append(
            {
                "path": relative,
                "sha256": digest.hexdigest(),
                "size_bytes": size,
            }
        )
    return entries


def write_inventory(path: Path, entries: list[dict]) -> None:
    payload = "".join(
        json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        for entry in entries
    )
    try:
        path.write_text(payload, encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot write inventory {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    args = parser.parse_args()

    try:
        entries = discover(args.dataset_root)
        write_inventory(args.output_jsonl, entries)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: discovered {len(entries)} MIDI files under {args.dataset_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
