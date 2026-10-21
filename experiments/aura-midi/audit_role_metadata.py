#!/usr/bin/env python3
"""
Musical Corpus Coverage Audit — Role/Genre Metadata Analysis
==============================================================
Analyzes existing corpora for musical role and genre coverage without
loading PyTorch or checkpoints. Uses manifests, metadata, and MIDI files.

Outputs: experiments/aura-midi/audit_report.json
"""

import os
import json
import csv
import yaml
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import sys

# Try to import pretty_midi for MIDI analysis
try:
    import pretty_midi
    PRETTY_MIDI_AVAILABLE = True
except ImportError:
    PRETTY_MIDI_AVAILABLE = False
    print("WARNING: pretty_midi not available. MIDI analysis will be limited.")

# Try to import mido as fallback
try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False


@dataclass
class CompositionStats:
    """Statistics for a single composition."""
    composition_id: str
    source: str
    midi_path: str
    num_tracks: int
    total_notes: int
    duration_sec: float
    tempo_bpm: Optional[float]
    pitch_range_min: Optional[int]
    pitch_range_max: Optional[int]
    max_simultaneous_notes: int
    programs: List[int]
    is_drum_tracks: List[bool]
    role_labels: Dict[str, str]
    genre_labels: List[str]
    license: str
    evidence_level: str


@dataclass
class CorpusSummary:
    """Summary statistics for a corpus."""
    source_name: str
    unique_compositions: int
    midi_files: int
    total_tracks: int
    total_notes: int
    avg_duration_sec: float
    avg_tempo_bpm: Optional[float]
    pitch_range_global: Dict[str, int]
    max_polyphony_global: int
    genre_labels_found: Dict[str, int]
    role_labels_found: Dict[str, int]
    programs_found: Dict[int, int]
    licenses: List[str]
    evidence_level: str
    notes: List[str]


def analyze_midi_file(midi_path: str) -> Dict[str, Any]:
    """Analyze a single MIDI file using pretty_midi or mido."""
    result = {
        "num_tracks": 0,
        "total_notes": 0,
        "duration_sec": 0.0,
        "tempo_bpm": None,
        "pitch_range_min": None,
        "pitch_range_max": None,
        "max_simultaneous_notes": 0,
        "programs": [],
        "is_drum_tracks": [],
        "notes_per_track": [],
        "error": None
    }

    if PRETTY_MIDI_AVAILABLE:
        try:
            pm = pretty_midi.PrettyMIDI(midi_path)
            result["duration_sec"] = pm.get_end_time()
            result["tempo_bpm"] = pm.estimate_tempo()
            result["num_tracks"] = len(pm.instruments)

            all_notes = []
            max_simul = 0

            for inst in pm.instruments:
                result["programs"].append(inst.program)
                result["is_drum_tracks"].append(inst.is_drum)
                notes = inst.notes
                result["notes_per_track"].append(len(notes))
                result["total_notes"] += len(notes)
                all_notes.extend(notes)

                if notes:
                    pitches = [n.pitch for n in notes]
                    if result["pitch_range_min"] is None or min(pitches) < result["pitch_range_min"]:
                        result["pitch_range_min"] = min(pitches)
                    if result["pitch_range_max"] is None or max(pitches) > result["pitch_range_max"]:
                        result["pitch_range_max"] = max(pitches)

            # Calculate max simultaneous notes (polyphony)
            if all_notes:
                events = []
                for n in all_notes:
                    events.append((n.start, 1))
                    events.append((n.end, -1))
                events.sort(key=lambda x: (x[0], -x[1]))

                current = 0
                for _, delta in events:
                    current += delta
                    if current > max_simul:
                        max_simul = current
                result["max_simultaneous_notes"] = max_simul

        except Exception as e:
            result["error"] = f"pretty_midi error: {str(e)}"

    elif MIDO_AVAILABLE:
        try:
            mid = mido.MidiFile(midi_path)
            result["duration_sec"] = mid.length
            result["num_tracks"] = len(mid.tracks)

            for track in mid.tracks:
                track_notes = 0
                track_program = 0
                is_drum = False
                for msg in track:
                    if msg.type == 'program_change':
                        track_program = msg.program
                    if msg.type == 'note_on' and msg.velocity > 0:
                        track_notes += 1
                result["programs"].append(track_program)
                result["is_drum_tracks"].append(is_drum)
                result["notes_per_track"].append(track_notes)
                result["total_notes"] += track_notes

        except Exception as e:
            result["error"] = f"mido error: {str(e)}"

    else:
        result["error"] = "No MIDI library available"

    return result