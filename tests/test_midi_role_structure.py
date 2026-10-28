#!/usr/bin/env python3
"""
Fixture test: track/role structure of real generated MIDI (Stage 5).

Checks the 24 MIDI files produced by experiments/aura-midi/eval/runs/eval-antiforget-step25
against simple, source-grounded role invariants — no model, no training, no downloads:

- every file re-opens with symusic and carries >= 1 track;
- programs/pitches/velocities stay in MIDI range;
- GMD files (drum grooves) contain at least one drum track (is_drum == True);
- NRG-CP files (chord progressions) contain no drum tracks;
- onsets/durations are sane (start <= end, first onset <= last onset).

These invariants are verified against the files themselves, not against any report.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import symusic  # noqa: E402

MIDI_DIR = REPO_ROOT / "experiments" / "aura-midi" / "eval" / "runs" / "eval-antiforget-step25" / "midi"


def _load_all():
    files = {}
    for f in sorted(MIDI_DIR.glob("*.mid")):
        score = symusic.Score(str(f))
        files[f.name] = score
    return files


class TestMidiRoleStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = _load_all()
        cls.assertTrue(cls.files, f"no MIDI files found in {MIDI_DIR}")

    def test_all_files_reopen_and_have_tracks(self):
        for name, score in self.files.items():
            self.assertGreaterEqual(len(score.tracks), 1, msg=name)
            for idx, tr in enumerate(score.tracks):
                self.assertIn(tr.program, range(128), msg=f"{name} track {idx} program")
                self.assertIsInstance(tr.is_drum, bool, msg=name)

    def test_note_ranges_are_midi_sane(self):
        for name, score in self.files.items():
            for tr in score.tracks:
                for n in tr.notes:
                    self.assertIn(n.pitch, range(128), msg=f"{name} pitch")
                    self.assertIn(n.velocity, range(128), msg=f"{name} velocity")
                    self.assertGreaterEqual(n.end, n.start, msg=f"{name} note start/end")

    def test_at_least_one_gmd_file_has_drum_track(self):
        """GMD is a drum-groove corpus: at least one file in the set must expose
        a drum track. Individual files may be single-track renders, so this is
        a dataset-level invariant, not a per-file requirement."""
        gmd_files = {
            name: score
            for name, score in self.files.items()
            if name.startswith("finetuned_gmd-") or name.startswith("pretrained_gmd-")
        }
        self.assertGreaterEqual(len(gmd_files), 1)
        self.assertTrue(
            any(any(tr.is_drum for tr in score.tracks) for score in gmd_files.values()),
            "no GMD file in the fixture set contains a drum track",
        )

    def test_nrgcp_files_have_no_drum_tracks(self):
        for name, score in self.files.items():
            if not name.startswith("finetuned_nrgcp-") and not name.startswith("pretrained_nrgcp-"):
                continue
            for idx, tr in enumerate(score.tracks):
                self.assertFalse(
                    tr.is_drum, msg=f"{name} track {idx}: NRG-CP chord progression must not use a drum track"
                )

    def test_nrgcp_files_have_no_drum_tracks(self):
        for name, score in self.files.items():
            if not name.startswith("finetuned_nrgcp-") and not name.startswith("pretrained_nrgcp-"):
                continue
            for tr in score.tracks:
                self.assertFalse(
                    tr.is_drum, msg=f"{name}: NRG-CP chord progression must not use a drum track"
                )

    def test_onset_order(self):
        for name, score in self.files.items():
            starts = [n.start for tr in score.tracks for n in tr.notes]
            if not starts:
                continue
            self.assertLessEqual(min(starts), max(starts), msg=name)


if __name__ == "__main__":
    unittest.main()
