"""
Pre-tokenize a bounded subset of NRG-CP and GMD MIDI files for the pilot training run.
Saves token ID sequences to a JSON cache for fast loading during training.
"""
import sys, json, time
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart")
MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"
RUNS_DIR = REPO_ROOT / "experiments" / "aura-midi" / "runs"

sys.path.insert(0, str(MODEL_DIR))

from miditok import MusicTokenizer
import symusic

print("Loading tokenizer...")
tokenizer = MusicTokenizer.from_pretrained(str(MODEL_DIR))
print(f"Tokenizer vocab_size: {tokenizer.vocab_size}")

SEQ_LEN = 128

def load_file_list(path):
    files = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                p = Path(line)
                if not p.is_absolute():
                    p = REPO_ROOT / p
                if p.exists():
                    files.append(str(p))
    return files

def tokenize_file(fpath, seq_len):
    """Tokenize a single MIDI file and return list of token ID sequences (windows)."""
    try:
        score = symusic.Score(fpath)
        tokens = tokenizer.encode(score)
        ids = tokens.ids
        if len(ids) < seq_len + 1:
            return []
        windows = []
        for i in range(0, len(ids) - seq_len, seq_len):
            windows.append(ids[i:i + seq_len + 1])
        return windows
    except Exception as e:
        print(f"  Skipping {fpath}: {e}")
        return []

# Load file lists (limited subset for pilot)
nrgcp_train = load_file_list(str(RUNS_DIR / "nrgcp_train_files.txt"))[:300]
nrgcp_val = load_file_list(str(RUNS_DIR / "nrgcp_val_files.txt"))[:100]
gmd_train = load_file_list(str(RUNS_DIR / "gmd_train_files.txt"))[:300]
gmd_val = load_file_list(str(RUNS_DIR / "gmd_val_files.txt"))[:100]

print(f"NRG-CP train: {len(nrgcp_train)} files, val: {len(nrgcp_val)} files")
print(f"GMD train: {len(gmd_train)} files, val: {len(gmd_val)} files")

# Pre-tokenize
cache_dir = Path(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\runs\pilot-20261027_145544")
cache_dir.mkdir(parents=True, exist_ok=True)

def build_cache(name, file_list):
    print(f"\nTokenizing {name} ({len(file_list)} files)...")
    start = time.time()
    all_windows = []
    for i, fpath in enumerate(file_list):
        windows = tokenize_file(fpath, SEQ_LEN)
        all_windows.extend(windows)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(file_list)} files, {len(all_windows)} windows so far")
    elapsed = time.time() - start
    print(f"  {name}: {len(all_windows)} windows in {elapsed:.1f}s")
    return all_windows

cache = {
    "seq_len": SEQ_LEN,
    "vocab_size": tokenizer.vocab_size,
    "nrgcp_train": build_cache("NRG-CP train", nrgcp_train),
    "nrgcp_val": build_cache("NRG-CP val", nrgcp_val),
    "gmd_train": build_cache("GMD train", gmd_train),
    "gmd_val": build_cache("GMD val", gmd_val),
}

cache_path = cache_dir / "token_cache.json"
tmp_path = str(cache_path) + ".tmp"
with open(tmp_path, "w") as f:
    json.dump(cache, f)
import shutil
shutil.move(tmp_path, str(cache_path))

# Verify cache integrity
with open(cache_path, "r") as f:
    verify = json.load(f)

print("\n=== Cache Summary ===")
for key in ["nrgcp_train", "nrgcp_val", "gmd_train", "gmd_val"]:
    print(f"  {key}: {len(verify[key])} windows")
print(f"Cache saved to: {cache_path}")
print("Pre-tokenization complete.")