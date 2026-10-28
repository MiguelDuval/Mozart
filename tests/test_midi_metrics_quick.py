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


if __name__ == "__main__":
    unittest.main()
