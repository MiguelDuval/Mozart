#!/usr/bin/env python3
"""
Generate golden fixtures for REMI/BPE tokenizer testing.
Uses the actual MidiTok tokenizer to encode/decode and produce reference outputs.
"""
import json
import os
import sys

TOKENIZER_PATH = 'C:/Users/migue/.cline/data/workspaces/chat/Mozart/experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json'
OUTPUT_DIR = 'C:/Users/migue/.cline/data/workspaces/chat/Mozart/tests/fixtures'


def main():
    try:
        from miditok import REMI
    except ImportError:
        print("MidiTok not available, skipping golden fixture generation.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load tokenizer
    tokenizer = REMI(params=TOKENIZER_PATH)
    print(f"Tokenizer loaded: {type(tokenizer).__name__}")
    print(f"Vocab size: {tokenizer.vocab_size}")

    vocab = tokenizer.vocab
    print(f"Named vocab size: {len(vocab)}")

    # Save named vocabulary as JSON fixture
    vocab_items = sorted(vocab.items(), key=lambda x: x[1])
    vocab_fixture = {
        "tokenizer_path": TOKENIZER_PATH,
        "vocab_size": tokenizer.vocab_size,
        "named_vocab_size": len(vocab),
        "tokens": [{"id": tid, "name": name} for name, tid in vocab_items]
    }
    with open(os.path.join(OUTPUT_DIR, 'vocab_fixture.json'), 'w') as f:
        json.dump(vocab_fixture, f, indent=2)
    print(f"Saved vocab fixture with {len(vocab_items)} tokens")

    # Print special tokens
    special = ['PAD_None', 'BOS_None', 'EOS_None', 'MASK_None']
    for name in special:
        if name in vocab:
            print(f"  {name} = {vocab[name]}")

    # Print some musical tokens
    for name in ['Pitch_60', 'Pitch_64', 'Pitch_67', 'Velocity_100', 'Bar_None', 'Program_0']:
        if name in vocab:
            print(f"  {name} = {vocab[name]}")

    # Test encoding/decoding a simple sequence
    # Create a simple token sequence (token names)
    test_sequence_names = [
        'BOS_None', 'Bar_None', 'Position_0', 'Pitch_60', 'Velocity_100',
        'Position_8', 'Pitch_64', 'Position_16', 'Pitch_67', 'Bar_None',
        'Position_0', 'Pitch_72', 'EOS_None'
    ]

    # Convert names to IDs using the tokenizer's vocab
    test_sequence_ids = []
    for name in test_sequence_names:
        if name in vocab:
            test_sequence_ids.append(vocab[name])
        else:
            print(f"WARNING: {name} not in vocab")

    print(f"\nTest sequence IDs: {test_sequence_ids}")

    # Save test sequence fixture
    sequence_fixture = {
        "token_names": test_sequence_names,
        "token_ids": test_sequence_ids
    }
    with open(os.path.join(OUTPUT_DIR, 'test_sequence.json'), 'w') as f:
        json.dump(sequence_fixture, f, indent=2)
    print(f"Saved test sequence fixture")

    # Try to decode using the tokenizer if it supports decoding
    try:
        # Check if tokenizer can decode IDs back to tokens
        decoded_names = [tokenizer.id_to_token[tid] for tid in test_sequence_ids if tid in tokenizer.id_to_token]
        print(f"Decoded names from IDs: {decoded_names[:5]}...")
    except Exception as e:
        print(f"Could not decode via id_to_token: {e}")

    print("\nGolden fixtures generated successfully.")


if __name__ == '__main__':
    main()