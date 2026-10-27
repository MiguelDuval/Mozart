"""Lightweight tests for musical-time comparisons across different TPQ values.

Verifies that the analysis normalizes tick-based MIDI into beats and seconds
so that the same musical content measured at different TPQ yields identical
musical duration (beats/seconds). Different TPQ must not be mistaken for
different musical timing.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

import symusic  # noqa: E402
from evaluate_models import score_metrics, extract_notes, ticks_to_seconds, tempo_map  # noqa: E402


def make_score(tpq):
    """Build a one-track score with fixed musical content at a given TPQ.

    Notes at beats 0, 1, 2 (quarter-note spaced) with a constant 120 BPM tempo.
    Duration in beats should be identical regardless of TPQ.
    """
    score = symusic.Score()
    score.tpq = tpq
    track = symusic.Track(name="t", program=0, is_drum=False)
    # tempo: 120 qpm at tick 0
    score.tempos.append(symusic.Tempo(0, 120, 500000))
    for beat in (0, 1, 2):
        start = beat * tpq
        end = start + tpq  # one quarter note long
        n = symusic.Note(time=start, duration=tpq, pitch=60, velocity=100)
        track.notes.append(n)
    score.tracks.append(track)
    return score


class TestMusicalTimeTPQ(unittest.TestCase):
    def test_ticks_to_seconds_normalizes_tpq(self):
        # 1 beat at 120 BPM = 0.5 s, regardless of TPQ.
        for tpq in (24, 96, 384, 1024):
            tick = tpq  # one beat
            tm = [(0, 120.0)]
            secs = ticks_to_seconds(tick, tm, tpq)
            self.assertAlmostEqual(secs, 0.5, places=6, msg=f"tpq={tpq}")

    def test_score_metrics_normalizes_tpq(self):
        for tpq in (24, 96, 384, 1024):
            score = make_score(tpq)
            m = score_metrics(score)
            # 3 quarter notes back-to-back = 3 beats; at 120 BPM = 1.5 s.
            self.assertAlmostEqual(m["duration_beats"], 3.0, places=6, msg=f"tpq={tpq}")
            self.assertAlmostEqual(m["duration_sec"], 1.5, places=6, msg=f"tpq={tpq}")
            self.assertEqual(m["tpq"], tpq)
            self.assertEqual(m["num_notes"], 3)

    def test_extract_notes_beat_fields_scale_with_tpq(self):
        for tpq in (24, 96):
            score = make_score(tpq)
            notes = extract_notes(score)
            # Each note is one quarter note = 1 beat long, in beats.
            self.assertEqual(len(notes), 3)
            for i, n in enumerate(notes):
                self.assertAlmostEqual(n["start_beats"], i, places=6, msg=f"tpq={tpq} note {i}")
                self.assertAlmostEqual(n["duration_beats"], 1.0, places=6, msg=f"tpq={tpq} note {i}")


if __name__ == "__main__":
    unittest.main()
