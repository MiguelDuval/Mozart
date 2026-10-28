#!/usr/bin/env python3
"""
Quick regression tests for MIDI evaluation robustness (Stage 2).

Covers error handling for missing/truncated MIDI and empty scores — paths the
evaluators (evaluate_models.midi_valid_and_reopenable, score_metrics) must
handle without crashing.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import symusic  # noqa: E402
from evaluate_models import midi_valid_and_reopenable, score_metrics  # noqa: E402


class TestMidiReopenErrorHandling(unittest.TestCase):
    def test_missing_file_is_not_valid(self):
        result = midi_valid_and_reopenable(Path("does_not_exist.mid"))
        self.assertFalse(result["valid"])
        self.assertFalse(result["reopened"])
        self.assertIn("error", result)

    def test_empty_score_metrics_do_not_crash(self):
        score = symusic.Score()
        metrics = score_metrics(score)
        self.assertEqual(metrics["num_notes"], 0)
        self.assertEqual(metrics["duration_beats"], 0.0)
        self.assertEqual(metrics["density_notes_per_beat"], 0.0)
        self.assertEqual(metrics["max_polyphony"], 0)
        self.assertEqual(metrics["num_tracks"], 0)

    def test_score_with_one_note(self):
        score = symusic.Score()
        track = symusic.Track(program=0, is_drum=False, name="Piano")
        track.notes.append(symusic.Note(time=0, duration=8, pitch=60, velocity=100))
        score.tracks.append(track)
        metrics = score_metrics(score)
        self.assertEqual(metrics["num_notes"], 1)
        self.assertAlmostEqual(metrics["duration_beats"], round(8.0 / score.tpq, 4))
        self.assertEqual(metrics["max_polyphony"], 1)


class TestTrackRoleMapping(unittest.TestCase):
    """_track_role maps GM program + is_drum to a coarse musical role.
    Not ground truth — only an instrument hint for evaluation reporting."""

    def test_drum_track_is_rhythm(self):
        from evaluate_models import _track_role
        self.assertEqual(_track_role(0, True), "rhythm")
        self.assertEqual(_track_role(127, True), "rhythm")

    def test_bass_program_range(self):
        from evaluate_models import _track_role
        for p in range(32, 40):
            self.assertEqual(_track_role(p, False), "bass")

    def test_lead_program_range(self):
        from evaluate_models import _track_role
        for p in range(80, 88):
            self.assertEqual(_track_role(p, False), "lead")

    def test_pad_program_range(self):
        from evaluate_models import _track_role
        for p in range(88, 96):
            self.assertEqual(_track_role(p, False), "pad")

    def test_harmony_program_ranges(self):
        from evaluate_models import _track_role
        for p in list(range(0, 8)) + list(range(24, 32)):
            self.assertEqual(_track_role(p, False), "harmony")

    def test_other_for_unmapped_programs(self):
        from evaluate_models import _track_role
        self.assertEqual(_track_role(40, False), "other")
        self.assertEqual(_track_role(96, False), "other")
        self.assertEqual(_track_role(127, False), "other")


class TestRoleHintMatching(unittest.TestCase):
    """_role_hint_matches compares declared role_hint with observed track roles.
    Role hints are free-text dataset labels — coarse sanity check only."""

    def test_drum_hint_matches_rhythm_track(self):
        from evaluate_models import _role_hint_matches
        self.assertTrue(_role_hint_matches("drum-oriented", ["rhythm"]))
        self.assertTrue(_role_hint_matches("Drums", ["rhythm"]))

    def test_chord_hint_matches_harmony_track(self):
        from evaluate_models import _role_hint_matches
        self.assertTrue(_role_hint_matches("chord-oriented", ["harmony"]))
        self.assertTrue(_role_hint_matches("Chords/Harmony", ["harmony"]))

    def test_bass_hint_matches_bass_track(self):
        from evaluate_models import _role_hint_matches
        self.assertTrue(_role_hint_matches("bass", ["bass"]))

    def test_lead_hint_matches_lead_track(self):
        from evaluate_models import _role_hint_matches
        self.assertTrue(_role_hint_matches("lead", ["lead"]))
        self.assertTrue(_role_hint_matches("melody", ["lead"]))

    def test_pad_hint_matches_pad_track(self):
        from evaluate_models import _role_hint_matches
        self.assertTrue(_role_hint_matches("pad", ["pad"]))

    def test_mismatched_hint_returns_false(self):
        from evaluate_models import _role_hint_matches
        self.assertFalse(_role_hint_matches("drum-oriented", ["harmony", "bass"]))
        self.assertFalse(_role_hint_matches("bass", ["lead", "pad"]))

    def test_empty_track_roles_returns_none(self):
        from evaluate_models import _role_hint_matches
        self.assertIsNone(_role_hint_matches("drum-oriented", []))
        self.assertIsNone(_role_hint_matches("bass", []))

    def test_unrecognized_hint_returns_none(self):
        from evaluate_models import _role_hint_matches
        self.assertIsNone(_role_hint_matches("unknown-style", ["rhythm"]))
        self.assertIsNone(_role_hint_matches("", ["bass"]))


if __name__ == "__main__":
    unittest.main()
