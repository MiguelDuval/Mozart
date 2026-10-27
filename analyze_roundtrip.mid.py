"""Analyze the test_roundtrip.mid file and compare with original."""
import symusic
from pathlib import Path

print("=" * 60)
print("ANALYZING test_roundtrip.mid (reconstructed MIDI)")
print("=" * 60)

# Load the reconstructed MIDI
reconstructed = symusic.Score(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\test_roundtrip.mid')
print(f"\nScore tpq: {reconstructed.tpq}")
print(f"Number of tracks: {len(reconstructed.tracks)}")
total_notes = sum(len(t.notes) for t in reconstructed.tracks)
print(f"Total notes: {total_notes}")

for i, track in enumerate(reconstructed.tracks):
    print(f"\nTrack {i}:")
    print(f"  program={track.program}, is_drum={track.is_drum}, notes={len(track.notes)}")
    if track.notes:
        pitches = [n.pitch for n in track.notes]
        velocities = [n.velocity for n in track.notes]
        start_times = [n.time for n in track.notes]
        end_times = [n.time + n.duration for n in track.notes]
        print(f"  Pitch range: {min(pitches)}-{max(pitches)}")
        print(f"  Velocity range: {min(velocities)}-{max(velocities)}")
        print(f"  Time range: {min(start_times)}-{max(end_times)} ticks")
        print(f"  Duration: {max(end_times) - min(start_times)} ticks")

# Now let's try to find the original MIDI
# The context mentions 4,929 tokens originally, 487 notes reconstructed, 1,692 tokens re-encoded
# Let's check the NRG-CP dataset for a file that might match
print("\n" + "=" * 60)
print("SEARCHING FOR ORIGINAL MIDI FILE")
print("=" * 60)

# The reconstructed has 487 notes - let's find an original with similar note count
midi_dir = Path(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\datasets\NRG-CP\extracted')
midi_files = list(midi_dir.glob('*.mid'))

for mf in midi_files[:20]:  # Check first 20
    s = symusic.Score(str(mf))
    notes = sum(len(t.notes) for t in s.tracks)
    if notes > 400:
        print(f"  {mf.name}: {notes} notes, {len(s.tracks)} tracks")

# Also check GMD dataset
print("\n--- GMD dataset ---")
gmd_dir = Path(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\datasets\GMD\extracted')
gmd_files = list(gmd_dir.rglob('*.mid'))
for mf in gmd_files[:20]:
    s = symusic.Score(str(mf))
    notes = sum(len(t.notes) for t in s.tracks)
    if notes > 400:
        print(f"  {mf.name}: {notes} notes, {len(s.tracks)} tracks")