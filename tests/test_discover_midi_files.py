#!/usr/bin/env python3
"""Tests for deterministic MIDI dataset discovery."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from discover_midi_files import discover, write_inventory


class DiscoverMidiFilesTests(unittest.TestCase):
    def test_discovery_is_recursive_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z").mkdir()
            (root / "a").mkdir()
            (root / "a" / "one.mid").write_bytes(b"one")
            (root / "z" / "two.MIDI").write_bytes(b"two")
            (root / "ignore.txt").write_text("ignore", encoding="utf-8")

            first = discover(root)
            second = discover(root)

            self.assertEqual(first, second)
            self.assertEqual(
                [entry["path"] for entry in first],
                ["a/one.mid", "z/two.MIDI"],
            )
            self.assertEqual(first[0]["size_bytes"], 3)
            self.assertEqual(
                first[0]["sha256"],
                hashlib.sha256(b"one").hexdigest(),
            )

    def test_empty_dataset_is_valid_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(discover(root), [])

    def test_inventory_jsonl_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture.mid").write_bytes(b"fixture")
            entries = discover(root)
            output = root / "inventory.jsonl"
            write_inventory(output, entries)

            expected = (
                json.dumps(entries[0], sort_keys=True)
                + "\n"
            )
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                expected,
            )


if __name__ == "__main__":
    unittest.main()
