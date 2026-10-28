#!/usr/bin/env python3
"""Test MMM v2 tokenizer round-trip on all Slakh samples."""
import sys
sys.path.insert(0, r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-multitrack-v2")

from tokenizer_mmm_v2 import MMMv2Tokenizer
import miditoolkit
from pathlib import Path

mmm = MMMv2Tokenizer(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official")

slakh_dir = Path(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\datasets\Slakh2100_samples")
midi_files = list(slakh_dir.rglob("all_src.mid"))
print(f"Found {len(midi_files)} MIDI files")

for i, midi_path in enumerate(midi_files):
    print(f"\n=== Test {i+1}: {midi_path.name} ===")
    original = miditoolkit.MidiFile(midi_path)
    print(f"Original tracks: {len(original.instruments)}")
    for j, inst in enumerate(original.instruments):
        print(f"  Track {j}: program={inst.program}, is_drum={inst.is_drum}, notes={len(inst.notes)}")
    
    tokens = mmm.encode_midi(midi_path)
    print(f"Encoded tokens: {len(tokens)}")
    regular = [t for t in tokens if t < 12000]
    special = [t for t in tokens if t >= 12000]
    print(f"Regular (0-11999): {len(regular)}, Special (>=12000): {special}")
    assert all(0 <= t < 12000 for t in regular), "Regular tokens out of range!"
    assert mmm.TRACK_START_ID in tokens, "Track_Start missing"
    assert mmm.TRACK_END_ID in tokens, "Track_End missing"
    track_starts = tokens.count(mmm.TRACK_START_ID)
    track_ends = tokens.count(mmm.TRACK_END_ID)
    print(f"Track_Start: {track_starts}, Track_End: {track_ends}")
    
    decoded = mmm.decode_tokens(tokens)
    print(f"Decoded tracks: {len(decoded.instruments)}")
    for j, inst in enumerate(decoded.instruments):
        print(f"  Track {j}: program={inst.program}, is_drum={inst.is_drum}, notes={len(inst.notes)}")
    
    orig_nonempty = sum(1 for inst in original.instruments if inst.notes)
    dec_nonempty = sum(1 for inst in decoded.instruments if inst.notes)
    print(f"Original non-empty: {orig_nonempty}, Decoded non-empty: {dec_nonempty}")
    assert orig_nonempty == dec_nonempty, f"Track count mismatch: {orig_nonempty} != {dec_nonempty}"
    print("✓ Round-trip track count preserved!")

print("\n✓ All round-trip tests passed!")