import hashlib
import os

# Checkpoint SHA256
with open("experiments/aura-midi/weights/auramidi_v1.pt", "rb") as f:
    h = hashlib.sha256()
    h.update(f.read())
    print(f"Checkpoint SHA256: {h.hexdigest()}")

# Find tokenizer files
print("\nTokenizer files:")
for root, dirs, files in os.walk("experiments/aura-midi"):
    for f in files:
        if "tokenizer" in f.lower() or f.endswith(".json"):
            fp = os.path.join(root, f)
            with open(fp, "rb") as fh:
                h = hashlib.sha256()
                h.update(fh.read())
                print(f"  {fp}: {h.hexdigest()} ({os.path.getsize(fp)} bytes)")