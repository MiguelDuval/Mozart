#!/usr/bin/env python3
"""Test miditok REMI tokenizer with fixed config."""

import sys
import json
print("Starting...")
sys.stdout.flush()

try:
    import miditok
    print(f"miditok imported: {miditok.__file__}")
    sys.stdout.flush()
except Exception as e:
    print(f"miditok import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from miditok import REMI, TokenizerConfig
    print("REMI imported")
    sys.stdout.flush()
except Exception as e:
    print(f"REMI import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Load config from tokenizer.json and fix time_signature_range
with open('experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json') as f:
    d = json.load(f)

config_dict = d['config']
print("Original time_signature_range:", config_dict.get('time_signature_range'))
print("Original beat_res:", config_dict.get('beat_res'))
print("Original additional_params:", config_dict.get('additional_params'))

# Fix time_signature_range: convert string keys to integers
old_ts_range = config_dict.get('time_signature_range', {})
new_ts_range = {}
for denom_str, numerators in old_ts_range.items():
    denom = int(denom_str)
    new_ts_range[denom] = numerators
config_dict['time_signature_range'] = new_ts_range
print("Fixed time_signature_range:", new_ts_range)

# Fix beat_res: convert string keys to tuples
old_beat_res = config_dict.get('beat_res', {})
new_beat_res = {}
for key_str, value in old_beat_res.items():
    parts = key_str.split('_')
    new_beat_res[(int(parts[0]), int(parts[1]))] = value
config_dict['beat_res'] = new_beat_res
print("Fixed beat_res:", new_beat_res)

# Fix beat_res_rest: convert string keys to tuples
old_beat_res_rest = config_dict.get('beat_res_rest', {})
new_beat_res_rest = {}
for key_str, value in old_beat_res_rest.items():
    parts = key_str.split('_')
    new_beat_res_rest[(int(parts[0]), int(parts[1]))] = value
config_dict['beat_res_rest'] = new_beat_res_rest
print("Fixed beat_res_rest:", new_beat_res_rest)

# Fix additional_params
additional_params = config_dict.get('additional_params', {})
additional_params.setdefault('add_trailing_bars', False)
additional_params.setdefault('max_bar_embedding', None)
additional_params.setdefault('use_bar_end_tokens', False)
print("Fixed additional_params:", additional_params)

# Create TokenizerConfig
config = TokenizerConfig(**config_dict)
config.additional_params = additional_params
print(f"TokenizerConfig created: {config}")

# Create REMI tokenizer
print("Creating REMI tokenizer...")
tokenizer = REMI(config)
print(f"REMI tokenizer created: {tokenizer}")

# Load the BPE model from JSON
print("Loading BPE model from tokenizer.json...")
tokenizer._load_from_json('experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json')

# IMPORTANT: Restore additional_params after _load_from_json overwrites config
tokenizer.config.additional_params = additional_params
print(f"Restored additional_params on tokenizer.config")

print(f"Loaded. vocab_size: {tokenizer.vocab_size}")
print(f"len(tokenizer): {len(tokenizer)}")

# Check internal state
print(f"\n_tpb_ticks_to_tokens keys: {list(tokenizer._tpb_ticks_to_tokens.keys())}")
for k, v in tokenizer._tpb_ticks_to_tokens.items():
    print(f"  TPB index {k}: {len(v)} durations, sample: {list(v.items())[:5]}")

print(f"\n_tpb_per_ts: {tokenizer._tpb_per_ts}")

# Test encoding a MIDI file
midi_path = 'experiments/aura-midi/datasets/gmd/extracted/groove/drummer1/session1/101_dance-disco_120_beat_4-4.mid'
print(f"\nEncoding: {midi_path}")
result = tokenizer.encode(midi_path)
ids = result.ids if hasattr(result, 'ids') else result
print(f"Encoded IDs (first 20): {ids[:20]}")
print(f"Total tokens: {len(ids)}")
print(f"Min ID: {min(ids)}, Max ID: {max(ids)}")

# Verify IDs are within vocab range
assert max(ids) < tokenizer.vocab_size, f"Max ID {max(ids)} >= vocab_size {tokenizer.vocab_size}"
assert min(ids) >= 0, f"Min ID {min(ids)} < 0"
print("[OK] All IDs within valid range")

# Test decoding
print("\nDecoding...")
decoded = tokenizer.decode(ids)
print(f"Decoded tracks: {len(decoded.tracks)}")
print(f"Total notes: {sum(len(tr.notes) for tr in decoded.tracks)}")

# Save decoded MIDI
output_path = 'test_roundtrip.mid'
decoded.dump_midi(output_path)
print(f"[OK] Saved decoded MIDI to {output_path}")

# Verify round-trip by reloading
print("\nVerifying round-trip...")
result2 = tokenizer.encode(output_path)
ids2 = result2.ids if hasattr(result2, 'ids') else result2
print(f"Round-trip tokens: {len(ids2)}")
print(f"Round-trip min/max: {min(ids2)}/{max(ids2)}")

print("\n[OK] ALL TOKENIZER TESTS PASSED")
sys.exit(0)