"""Compare the reconstructed test_roundtrip.mid with potential originals."""
import symusic
from pathlib import Path

print("=" * 60)
print("COMPARING RECONSTRUCTED WITH POTENTIAL ORIGINALS")
print("=" * 60)

# Load reconstructed
recon = symusic.Score(r'C:\Users\migue\.cline\data\workspaces\chat\Mozart\test_roundtrip.mid')
print(f"\nRECONSTRUCTED (test_roundtrip.mid):")
print(f"  tpq: {recon.tpq}")
print(f"  tracks: {len(recon.tracks)}, notes: {sum(len(t.notes) for t in recon.tracks)}")
t0 = recon.tracks[0]
print(f"  Track 0: program={t0.program}, is_drum={t0.is_drum}, notes={len(t0.notes)}")
if t0.notes:
    pitches = [n.pitch for n in t0.notes]
    velocities = [n.velocity for n in t0.notes]
    print(f"  Pitch range: {min(pitches)}-{max(pitches)}")
    print(f"  Velocity range: {min(velocities)}-{max(velocities)}")

# Check potential originals from GMD dataset
print("\n" + "-" * 60)
print("POTENTIAL ORIGINALS FROM GMD DATASET")
print("-" * 60)

gmd_dir = Path(r'C:\Users\migue\.cline\data\\workspaces\\chat\\Mozart\\experiments\\aura-midi\\datasets\\GMD\\extracted')
gmd_files = list(gmd_dir.rglob('*.mid'))

for mf in sorted(gmd_files)[:30]:
    s = symusic.Score(str(mf))
    notes = sum(len(t.notes) for t in s.tracks)
    if 400 <= notes <= 550:
        print(f"\n  {mf}:")
        print(f"    tpq: {s.tpq}")
        print(f"    tracks: {len(s.tracks)}, notes: {notes}")
        for i, track in enumerate(s.tracks):
            print(f"    Track {i}: program={track.program}, is_drum={track.is_drum}, notes={len(track.notes)}")
            if track.notes:
                pitches = [n.pitch for n in track.notes]
                velocities = [n.velocity for n in track.notes]
                print(f"      Pitch range: {min(pitches)}-{max(pitches)}")
                print(f"      Velocity range: {min(velocities)}-{max(velocities)}")