"""MIDI Round-Trip Fidelity Analysis
Analyzes the musical information loss when encoding and decoding MIDI
through the shikhr/music_maker tokenizer.
"""
import sys
sys.path.insert(0, r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official')

from miditok import MusicTokenizer
import symusic
from pathlib import Path
import json

print("=" * 60)
print("MIDI ROUND-TRIP FIDELITY ANALYSIS")
print("=" * 60)

# Load tokenizer
print("\nLoading tokenizer...")
tokenizer = MusicTokenizer.from_pretrained(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official')
print(f"Tokenizer vocab_size: {tokenizer.vocab_size}")

# Find a MIDI file to test
midi_dir = Path(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\datasets\NRG-CP\extracted')
midi_files = list(midi_dir.glob('*.mid'))
print(f"\nFound {len(midi_files)} MIDI files in NRG-CP")

# Test with the first file
test_midi = midi_files[0]
print(f"\n{'='*60}")
print(f"Testing with: {test_midi.name}")
print(f"{'='*60}")

# Load original MIDI with symusic
score = symusic.Score(str(test_midi))
print(f"\nORIGINAL MIDI:")
print(f"  File: {test_midi.name}")
print(f"  Score tpq: {score.tpq}")
print(f"  Number of tracks: {len(score.tracks)}")
total_notes = sum(len(t.notes) for t in score.tracks)
print(f"  Total notes: {total_notes}")

# Track details
for i, track in enumerate(score.tracks):
    print(f"  Track {i}: program={track.program}, is_drum={track.is_drum}, notes={len(track.notes)}")
    if track.notes:
        pitches = [n.pitch for n in track.notes]
        velocities = [n.velocity for n in track.notes]
        print(f"    Pitch range: {min(pitches)}-{max(pitches)}")
        print(f"    Velocity range: {min(velocities)}-{max(velocities)}")

# Encode MIDI to tokens
print("\nEncoding MIDI to tokens...")
tokens = tokenizer.encode(score)
print(f"  Token IDs length: {len(tokens.ids)}")
print(f"  First 20 IDs: {tokens.ids[:20]}")
print(f"  Max ID: {max(tokens.ids)}, Min ID: {min(tokens.ids)}")
print(f"  All IDs < 12000: {all(x < 12000 for x in tokens.ids)}")
print(f"  Unique tokens: {len(set(tokens.ids))}")

# Decode tokens back to MIDI
print("\nDecoding tokens back to MIDI...")
decoded_score = tokenizer.decode(tokens)
print(f"  Decoded score type: {type(decoded_score)}")
print(f"  Decoded tracks: {len(decoded_score.tracks)}")
total_decoded_notes = sum(len(t.notes) for t in decoded_score.tracks)
print(f"  Decoded notes: {total_decoded_notes}")

# Track details for decoded
for i, track in enumerate(decoded_score.tracks):
    print(f"  Track {i}: program={track.program}, is_drum={track.is_drum}, notes={len(track.notes)}")
    if track.notes:
        pitches = [n.pitch for n in track.notes]
        velocities = [n.velocity for n in track.notes]
        print(f"    Pitch range: {min(pitches)}-{max(pitches)}")
        print(f"    Velocity range: {min(velocities)}-{max(velocities)}")

# Save decoded MIDI for inspection (separate path from test_roundtrip.mid)
output_path = Path(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\midi_roundtrip_decoded.mid')
decoded_score.dump_midi(str(output_path))
print(f"\n  Saved decoded MIDI to: {output_path}")

# Re-encode the decoded MIDI
print("\nRe-encoding decoded MIDI...")
tokens2 = tokenizer.encode(decoded_score)
print(f"  Re-encoded token IDs length: {len(tokens2.ids)}")
print(f"  First 20 IDs: {tokens2.ids[:20]}")
print(f"  Max ID: {max(tokens2.ids)}, Min ID: {min(tokens2.ids)}")

# Summary
print("\n" + "=" * 60)
print("ROUND-TRIP SUMMARY")
print("=" * 60)
print(f"  Original tokens:  {len(tokens.ids)}")
print(f"  Decoded notes:    {total_decoded_notes}")
print(f"  Re-encoded tokens: {len(tokens2.ids)}")
print(f"  Original notes:   {total_notes}")
print(f"  Original tracks:  {len(score.tracks)}")
print(f"  Decoded tracks:   {len(decoded_score.tracks)}")
print(f"  Token reduction:  {len(tokens.ids) - len(tokens2.ids)} ({100*(len(tokens.ids)-len(tokens2.ids))/len(tokens.ids):.1f}%)")
print(f"  Note reduction:   {total_notes - total_decoded_notes} ({100*(total_notes-total_decoded_notes)/max(total_notes,1):.1f}%)")
print(f"  Track reduction:  {len(score.tracks) - len(decoded_score.tracks)}")

# Save results to JSON
results = {
    "midi_file": test_midi.name,
    "original_tokens": len(tokens.ids),
    "original_notes": total_notes,
    "original_tracks": len(score.tracks),
    "decoded_notes": total_decoded_notes,
    "decoded_tracks": len(decoded_score.tracks),
    "reencoded_tokens": len(tokens2.ids),
    "token_reduction": len(tokens.ids) - len(tokens2.ids),
    "note_reduction": total_notes - total_decoded_notes,
    "track_reduction": len(score.tracks) - len(decoded_score.tracks),
}

results_path = Path(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\midi_roundtrip_results.json')
with open(results_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to: {results_path}")

# Test with a few more files
print(f"\n{'='*60}")
print("ADDITIONAL FILES")
print(f"{'='*60}")
for i, mf in enumerate(midi_files[1:4]):
    print(f"\n--- File {i+2}: {mf.name} ---")
    s = symusic.Score(str(mf))
    tok = tokenizer.encode(s)
    dec = tokenizer.decode(tok)
    dec_notes = sum(len(t.notes) for t in dec.tracks)
    orig_notes = sum(len(t.notes) for t in s.tracks)
    print(f"  Original: {len(tok.ids)} tokens, {orig_notes} notes, {len(s.tracks)} tracks")
    print(f"  Decoded:  {len(dec.tracks)} tracks, {dec_notes} notes")
    print(f"  Re-encoded: {len(tokenizer.encode(dec).ids)} tokens")

print("\n" + "=" * 60)
print("ANALYSIS COMPLETE")
print("=" * 60)