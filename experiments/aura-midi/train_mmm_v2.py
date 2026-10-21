#!/usr/bin/env python3
"""
MMM v2 Multi-track Training Script.

Uses the official BPE tokenizer (vocab=12000) with Track_Start/Track_End markers.
Expands model to vocab_size=12002 preserving all 12000 pretrained embeddings.
"""
import os
import json
import math
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

import torch
import torch.nn as nn
from torch.nn import functional as F
from torch.utils.data import Dataset, DataLoader, IterableDataset

# Add project paths
import sys
sys.path.insert(0, r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official")

from gpt_model import GPT, GPTConfig
from mgpt_config import MGPTConfig

# ============================================================
# CONFIGURATION
# ============================================================

@dataclass
class TrainConfig:
    # Data
    data_dir: str = r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\datasets"
    manifest_train: str = "manifests/slakh_train.jsonl"
    manifest_val: str = "manifests/slakh_validation.jsonl"
    manifest_replay_nrg: str = "data_index.json"
    
    # Model - MMM v2: 12000 (official BPE) + 2 (Track_Start, Track_End)
    vocab_size: int = 12002
    block_size: int = 1024
    n_layer: int = 12
    n_head: int = 8
    n_embd: int = 512
    dropout: float = 0.1
    bias: bool = False
    
    # Training
    batch_size: int = 1
    grad_accum: int = 8
    max_steps: int = 10000
    lr: float = 3e-6
    min_lr: float = 1e-6
    warmup_steps: int = 500
    weight_decay: float = 0.1
    grad_clip: float = 1.0
    
    # Checkpointing
    save_every: int = 250
    eval_every: int = 250
    keep_last_n: int = 3
    
    # Run
    seed: int = 42
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    dtype: str = "fp32"
    run_name: str = "mmm-v2-multitrack-training"
    
    # Paths
    resume_from: str = r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\runs\broad-training-20261020_204942\checkpoint_best.pt"
    tokenizer_path: str = r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-multitrack-v2\tokenizer.json"
    output_dir: str = r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\runs"

    # Token IDs
    track_start_id: int = 12000
    track_end_id: int = 12001
    pad_token_id: int = 0
    bos_token_id: int = 1
    eos_token_id: int = 2

config = TrainConfig()

# ============================================================
# TOKENIZER WRAPPER
# ============================================================

class MMMv2Tokenizer:
    """
    MMM v2 Tokenizer wrapping the official BPE tokenizer.
    
    Vocabulary layout:
    - 0-11999: Original BPE tokenizer tokens (unchanged)
    - 12000: Track_Start
    - 12001: Track_End
    Total vocab size: 12002
    """
    
    def __init__(self, official_tokenizer_path: str):
        from miditok import MusicTokenizer
        import symusic
        
        print(f"Loading official tokenizer from {official_tokenizer_path}")
        self.base_tokenizer = MusicTokenizer.from_pretrained(official_tokenizer_path)
        self.hf_tokenizer = self.base_tokenizer._model
        print(f"Base tokenizer vocab size: {len(self.base_tokenizer)}")
        print(f"HF tokenizer vocab size: {self.hf_tokenizer.get_vocab_size()}")
        
        # Special token IDs
        self.TRACK_START_ID = config.track_start_id
        self.TRACK_END_ID = config.track_end_id
        self.VOCAB_SIZE = config.vocab_size
        
        # Base tokenizer special tokens
        self.pad_token_id = self.base_tokenizer.vocab['PAD_None']
        self.bos_token_id = self.base_tokenizer.vocab['BOS_None']
        self.eos_token_id = self.base_tokenizer.vocab['EOS_None']
        self.mask_token_id = self.base_tokenizer.vocab['MASK_None']
    
    def __len__(self) -> int:
        return self.VOCAB_SIZE
    
    @property
    def vocab_size(self) -> int:
        return self.VOCAB_SIZE
    
    def encode_midi(self, midi_path: str) -> List[int]:
        """
        Encode a multi-track MIDI file using the official BPE tokenizer.
        
        Note: The official tokenizer merges same-program tracks.
        Track_Start/Track_End are added at sequence boundaries.
        """
        import symusic
        import tempfile
        from miditoolkit import MidiFile
        
        # Load MIDI
        midi_file = MidiFile(midi_path)
        
        # Save to temp file for symusic
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            temp_path = f.name
        midi_file.dump(temp_path)
        
        score = symusic.Score(temp_path)
        import os
        os.unlink(temp_path)
        
        # Encode with official tokenizer (full sequence, merged tracks)
        tokens = self.base_tokenizer.encode(score)
        if isinstance(tokens, list) and len(tokens) > 0 and hasattr(tokens[0], 'ids'):
            token_ids = tokens[0].ids
        elif hasattr(tokens, 'ids'):
            token_ids = tokens.ids
        else:
            token_ids = tokens
        
        # Add Track_Start at beginning, Track_End at end
        full_sequence = [self.bos_token_id, self.TRACK_START_ID] + token_ids + [self.TRACK_END_ID, self.eos_token_id]
        
        return full_sequence


# ============================================================
# MODEL EXPANSION
# ============================================================

def expand_model_embeddings(model: GPT, new_vocab_size: int, track_start_id: int, track_end_id: int):
    """
    Expand model embeddings from 12000 to 12002.
    
    Preserves all 12000 original embedding rows.
    Initializes new rows for Track_Start and Track_End.
    Maintains weight tying between wte and lm_head.
    """
    old_vocab_size = model.transformer.wte.weight.shape[0]
    print(f"Expanding embeddings: {old_vocab_size} -> {new_vocab_size}")
    
    if old_vocab_size == new_vocab_size:
        print("Vocab size already matches, no expansion needed")
        return model
    
    assert old_vocab_size == 12000, f"Expected old vocab 12000, got {old_vocab_size}"
    assert new_vocab_size == 12002, f"Expected new vocab 12002, got {new_vocab_size}"
    
    # Save original embeddings for verification
    original_wte = model.transformer.wte.weight.data.clone()
    original_lm_head = model.lm_head.weight.data.clone()
    
    # Verify weight tying before expansion
    print(f"Weight tying before: {model.transformer.wte.weight is model.lm_head.weight}")
    
    # Create new embedding matrix
    new_wte = nn.Embedding(new_vocab_size, model.config.n_embd)
    new_lm_head = nn.Linear(model.config.n_embd, new_vocab_size, bias=False)
    
    # Copy original embeddings (0-11999)
    with torch.no_grad():
        new_wte.weight[:old_vocab_size] = original_wte
        new_lm_head.weight[:old_vocab_size] = original_lm_head
        
        # Initialize new embeddings (12000, 12001) with small random values
        nn.init.normal_(new_wte.weight[old_vocab_size:], mean=0.0, std=0.02)
        nn.init.normal_(new_lm_head.weight[old_vocab_size:], mean=0.0, std=0.02)
        
        print(f"Initialized Track_Start (id={track_start_id}) embedding")
        print(f"Initialized Track_End (id={track_end_id}) embedding")
    
    # Replace embeddings with weight tying
    model.transformer.wte = new_wte
    model.lm_head = new_lm_head
    
    # Ensure weight tying
    model.lm_head.weight = model.transformer.wte.weight
    
    # Verify
    print(f"Weight tying after: {model.transformer.wte.weight is model.lm_head.weight}")
    print(f"New vocab size: {model.transformer.wte.weight.shape[0]}")
    
    # Verify original embeddings preserved exactly
    with torch.no_grad():
        diff = (model.transformer.wte.weight[:old_vocab_size] - original_wte).abs().max().item()
        print(f"Max diff in preserved embeddings: {diff}")
        assert diff == 0.0, "Original embeddings not preserved!"
    
    # Update config
    model.config.vocab_size = new_vocab_size
    
    return model


def load_phase1_checkpoint(model: GPT, checkpoint_path: str, new_vocab_size: int):
    """Load Phase 1 checkpoint and expand embeddings."""
    print(f"Loading checkpoint from {checkpoint_path}")
    
    ckpt = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    
    # Extract model state dict
    if 'model' in ckpt:
        state_dict = ckpt['model']
    else:
        state_dict = ckpt
    
    # Load with strict=False to handle vocab size mismatch
    missing_keys, unexpected_keys = model.load_state_dict(state_dict, strict=False)
    
    print(f"Missing keys: {missing_keys}")
    print(f"Unexpected keys: {unexpected_keys}")
    
    # The missing keys should be transformer.wte.weight and lm_head.weight
    embedding_keys = [k for k in missing_keys if 'wte' in k or 'lm_head' in k]
    other_missing = [k for k in missing_keys if k not in embedding_keys]
    
    if other_missing:
        print(f"WARNING: Other missing keys: {other_missing}")
    
    # Expand embeddings
    model = expand_model_embeddings(model, new_vocab_size, config.track_start_id, config.track_end_id)
    
    # Verify checkpoint loading
    step = ckpt.get('step', 0)
    val_loss = ckpt.get('val_loss', float('inf'))
    print(f"Checkpoint step: {step}, val_loss: {val_loss:.4f}")
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    return model, step, val_loss


# ============================================================
# DATA LOADING
# ============================================================

class MIDIDataset(IterableDataset):
    """Dataset for multi-track MIDI files."""
    
    def __init__(self, manifest_path: str, tokenizer: MMMv2Tokenizer, block_size: int, shuffle: bool = True):
        self.manifest_path = Path(manifest_path)
        self.tokenizer = tokenizer
        self.block_size = block_size
        self.shuffle = shuffle
        self.samples = self._load_manifest()
    
    def _load_manifest(self):
        samples = []
        with open(self.manifest_path) as f:
            for line in f:
                data = json.loads(line.strip())
                samples.append(data)
        print(f"Loaded {len(samples)} samples from {self.manifest_path}")
        return samples
    
    def __iter__(self):
        if self.shuffle:
            import random
            random.shuffle(self.samples)
        
        for sample in self.samples:
            midi_path = sample['midi_path']
            try:
                token_ids = self.tokenizer.encode_midi(midi_path)
                
                for i in range(0, len(token_ids), self.block_size):
                    block = token_ids[i:i + self.block_size]
                    if len(block) < self.block_size:
                        block = block + [self.tokenizer.pad_token_id] * (self.block_size - len(block))
                    
                    x = torch.tensor(block[:-1], dtype=torch.long)
                    y = torch.tensor(block[1:], dtype=torch.long)
                    yield x, y
                    
            except Exception as e:
                print(f"Error processing {midi_path}: {e}")
                continue


# ============================================================
# MODEL CREATION
# ============================================================

def create_model(config: TrainConfig) -> GPT:
    """Create GPT model with MMM v2 config."""
    gpt_config = GPTConfig(
        vocab_size=config.vocab_size,
        block_size=config.block_size,
        n_layer=config.n_layer,
        n_head=config.n_head,
        n_embd=config.n_embd,
        dropout=config.dropout,
        bias=config.bias,
    )
    model = GPT(gpt_config)
    return model


# ============================================================
# TRAINING
# ============================================================

def train(config: TrainConfig):
    torch.manual_seed(config.seed)
    torch.cuda.manual_seed(config.seed)
    
    # Create model
    print("Creating model...")
    model = create_model(config)
    print(f"Model created with {sum(p.numel() for p in model.parameters()):,} parameters")
    
    # Load Phase 1 checkpoint and expand embeddings
    model, start_step, best_val_loss = load_phase1_checkpoint(model, config.resume_from, config.vocab_size)
    
    model.to(config.device)
    model.train()
    
    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.lr,
        weight_decay=config.weight_decay,
        betas=(0.9, 0.95),
    )
    
    # Scheduler
    def lr_lambda(step):
        if step < config.warmup_steps:
            return step / config.warmup_steps
        progress = (step - config.warmup_steps) / (config.max_steps - config.warmup_steps)
        return config.min_lr / config.lr + 0.5 * (1 - config.min_lr / config.lr) * (1 + math.cos(math.pi * progress))
    
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    
    # Load optimizer/scheduler state if available
    ckpt = torch.load(config.resume_from, map_location='cpu', weights_only=True)
    if 'optimizer' in ckpt:
        optimizer.load_state_dict(ckpt['optimizer'])
    if 'scheduler' in ckpt:
        scheduler.load_state_dict(ckpt['scheduler'])
    
    # Tokenizer
    print("Loading tokenizer...")
    tokenizer = MMMv2Tokenizer(
        r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official"
    )
    
    # Data loaders
    print("Loading data...")
    train_dataset = MIDIDataset(
        Path(config.data_dir) / config.manifest_train,
        tokenizer, config.block_size, shuffle=True
    )
    val_dataset = MIDIDataset(
        Path(config.data_dir) / config.manifest_val,
        tokenizer, config.block_size, shuffle=False
    )
    
    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, num_workers=0)
    
    # Run directory
    run_dir = Path(config.output_dir) / f"{config.run_name}-{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run directory: {run_dir}")
    
    with open(run_dir / "train_config.json", "w") as f:
        json.dump(config.__dict__, f, indent=2, default=str)
    
    step = start_step
    grad_accum_counter = 0
    
    print(f"Starting training from step {step}")
    print(f"Best val loss so far: {best_val_loss:.4f}")
    
    while step < config.max_steps:
        for x, y in train_loader:
            x, y = x.to(config.device), y.to(config.device)
            
            logits, loss = model(x, y)
            loss = loss / config.grad_accum
            
            loss.backward()
            grad_accum_counter += 1
            
            if grad_accum_counter == config.grad_accum:
                torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)
                
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                grad_accum_counter = 0
                step += 1
                
                if step % 10 == 0:
                    lr = scheduler.get_last_lr()[0]
                    print(f"Step {step}: loss={loss.item()*config.grad_accum:.4f}, lr={lr:.2e}")
                
                if step % config.eval_every == 0:
                    val_loss = evaluate(model, val_loader, config)
                    print(f"Step {step}: val_loss={val_loss:.4f}")
                    
                    if val_loss < best_val_loss:
                        best_val_loss = val_loss
                        save_checkpoint(model, optimizer, scheduler, step, val_loss, run_dir, "best")
                        print(f"  New best val loss: {best_val_loss:.4f}")
                    
                    save_checkpoint(model, optimizer, scheduler, step, val_loss, run_dir, "last")
                
                if step % config.save_every == 0:
                    save_checkpoint(model, optimizer, scheduler, step, val_loss, run_dir, f"step_{step}")
                
                if step >= config.max_steps:
                    break
        
        if step >= config.max_steps:
            break
    
    print("Training complete!")
    save_checkpoint(model, optimizer, scheduler, step, val_loss, run_dir, "final")


def evaluate(model, val_loader, config):
    model.eval()
    total_loss = 0
    count = 0
    with torch.no_grad():
        for x, y in val_loader:
            x, y = x.to(config.device), y.to(config.device)
            _, loss = model(x, y)
            total_loss += loss.item()
            count += 1
            if count >= 50:
                break
    model.train()
    return total_loss / max(1, count)


def save_checkpoint(model, optimizer, scheduler, step, val_loss, run_dir, name):
    ckpt = {
        'model': model.state_dict(),
        'optimizer': optimizer.state_dict(),
        'scheduler': scheduler.state_dict(),
        'step': step,
        'val_loss': val_loss,
        'config': model.config.__dict__,
    }
    path = run_dir / f"checkpoint_{name}.pt"
    torch.save(ckpt, path)
    
    checkpoints = sorted(run_dir.glob("checkpoint_step_*.pt"), key=lambda p: p.stat().st_mtime)
    while len(checkpoints) > config.keep_last_n:
        checkpoints.pop(0).unlink()


if __name__ == "__main__":
    train(config)