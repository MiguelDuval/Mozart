#!/usr/bin/env python3
"""Test tokenizer and model loading without miditok MusicTokenizer."""

import json
import time
import sys

print("Loading tokenizer from tokenizer.json...")
start = time.time()
d = json.load(open('experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json'))
print(f"JSON loaded in {time.time() - start:.2f}s")

print("Loading HuggingFace tokenizer...")
start = time.time()
from tokenizers import Tokenizer
hf_tokenizer = Tokenizer.from_str(d['_model'])
print(f"HF tokenizer loaded in {time.time() - start:.2f}s")
print(f"Vocab size: {hf_tokenizer.get_vocab_size()}")

# Test encoding/decoding with HF tokenizer
print("\nTesting HF tokenizer...")
result = hf_tokenizer.encode("hello world")
print(f"Encoded: {result.ids}")
decoded = hf_tokenizer.decode(result.ids)
print(f"Decoded: {decoded}")

# Load model config
print("\nLoading model config...")
with open('experiments/aura-midi/models/shikhr-music-maker-official/config.json') as f:
    config = json.load(f)
print(f"Config: {config}")

# Load model using safetensors
print("\nLoading model weights...")
start = time.time()
from safetensors.torch import load_file
state_dict = load_file('experiments/aura-midi/models/shikhr-music-maker-official/model.safetensors')
print(f"Model loaded in {time.time() - start:.2f}s")
print(f"All keys:")
for k in state_dict.keys():
    print(f"  {k}: {state_dict[k].shape}")

# Check lm_head and wte
if 'model.lm_head.weight' in state_dict:
    print(f"\nlm_head.shape: {state_dict['model.lm_head.weight'].shape}")
if 'model.transformer.wte.weight' in state_dict:
    print(f"wte.shape: {state_dict['model.transformer.wte.weight'].shape}")

# Check weight tying
import torch
if 'model.lm_head.weight' in state_dict and 'model.transformer.wte.weight' in state_dict:
    tied = state_dict['model.lm_head.weight'].data_ptr() == state_dict['model.transformer.wte.weight'].data_ptr()
    print(f"Weight tied (same data_ptr): {tied}")
    if not tied:
        equal = torch.allclose(state_dict['model.lm_head.weight'], state_dict['model.transformer.wte.weight'])
        print(f"Weight tied (values equal): {equal}")

print("\n[OK] BASIC CHECKS PASSED")
sys.exit(0)