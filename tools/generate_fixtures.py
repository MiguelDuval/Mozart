#!/usr/bin/env python3
"""
Generate golden fixtures for REMI/BPE tokenizer testing.
Uses the actual MidiTok tokenizer to encode/decode and produce reference outputs.
"""

import json
import sys
import os

def test_tokenizer_miditok():
    """Test using MidiTok directly."""
    try:
        from miditok import REMI
        from pathlib import Path
        
        tokenizer_path = '/Users/migue/.cline/data/workspaces/chat/Mozart/experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json'
        
        # Load tokenizer
        tokenizer = REMI(params=tokenizer_path)
        print(f"Tokenizer loaded: {tokenizer}")
        print(f"Vocab size: {tokenizer.vocab_size}")
        
        # Print all vocabulary
        print("\nAll vocabulary:")
        vocab = tokenizer.vocab
        for name, tid in sorted(vocab.items(), key=lambda x: x[1]):
            print(f"  {tid}: {name}")
        
    except ImportError as e:
        print(f"MidiTok not available: {e}")
        test_tokenizer_manual()

def test_tokenizer_manual():
    """Manual tokenizer testing without MidiTok."""
    tokenizer_path = '/Users/migue/.cline/data/workspaces/chat/Mozart/experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json'
    
    with open(tokenizer_path, 'r') as f:
        data = json.load(f)
    
    vocab_base = data['_vocab_base']
    byte_to_token = data['_vocab_base_byte_to_token']
    
    print(f"Base vocab size: {len(vocab_base)}")
    print(f"Byte to token mappings: {len(byte_to_token)}")
    
    # Print all base vocab
    print("\nBase vocabulary:")
    for name, tid in sorted(vocab_base.items(), key=lambda x: x[1]):
        print(f"  {tid}: {name}")

if __name__ == '__main__':
    test_tokenizer_miditok()