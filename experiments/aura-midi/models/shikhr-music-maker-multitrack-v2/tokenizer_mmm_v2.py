"""
MMM v2 Tokenizer - Multi-track Music Machine wrapping the official BPE tokenizer.

This tokenizer:
1. Loads the official pretrained BPE tokenizer (vocab=12000)
2. Adds Track_Start (ID=12000) and Track_End (ID=12001) as new special tokens
3. Encodes each track independently using the original BPE tokenizer
4. Wraps each track with Track_Start/Track_End markers
5. Preserves all original 12000 token IDs exactly
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from miditok import MusicTokenizer, REMI
from miditok.classes import TokSequence
from miditoolkit import MidiFile


class MMMv2Tokenizer:
    """
    Multi-track tokenizer wrapping the official BPE tokenizer.
    
    Vocabulary layout:
    - 0-11999: Original BPE tokenizer tokens (unchanged)
    - 12000: Track_Start
    - 12001: Track_End
    - 12002: Track_Program (followed by program number 0-127)
    - 12003: Track_IsDrum (followed by 0/1)
    Total vocab size: 12004
    """
    
    TRACK_START_ID = 12000
    TRACK_END_ID = 12001
    TRACK_PROGRAM_ID = 12002
    TRACK_IS_DRUM_ID = 12003
    VOCAB_SIZE = 12004
    
    def __init__(self, official_tokenizer_path: Union[str, Path]):
        """
        Initialize MMM v2 tokenizer.
        
        Args:
            official_tokenizer_path: Path to the official shikhr-music-maker-official tokenizer directory
        """
        self.official_tokenizer_path = Path(official_tokenizer_path)
        self.base_tokenizer: MusicTokenizer = None
        self._load_base_tokenizer()
        self._verify_vocab()
        
        # Special token mapping for MMM
        self.special_tokens = {
            'Track_Start': self.TRACK_START_ID,
            'Track_End': self.TRACK_END_ID,
            'Track_Program': self.TRACK_PROGRAM_ID,
            'Track_IsDrum': self.TRACK_IS_DRUM_ID,
        }
        
        # Reverse mapping for decoding
        self.id_to_special = {v: k for k, v in self.special_tokens.items()}
    
    def _load_base_tokenizer(self):
        """Load the official BPE tokenizer."""
        print(f"Loading official tokenizer from {self.official_tokenizer_path}")
        self.base_tokenizer = MusicTokenizer.from_pretrained(str(self.official_tokenizer_path))
        # The HF tokenizer is in _model attribute
        self.hf_tokenizer = self.base_tokenizer._model
        print(f"Base tokenizer vocab size: {len(self.base_tokenizer)}")
        print(f"Base special tokens: {self.base_tokenizer.special_tokens}")
        print(f"HF tokenizer vocab size: {self.hf_tokenizer.get_vocab_size()}")
    
    def _verify_vocab(self):
        """Verify the base tokenizer has expected vocab size."""
        vocab_size = len(self.base_tokenizer)
        if vocab_size != 12000:
            raise ValueError(f"Expected base vocab size 12000, got {vocab_size}")
        
        # Verify special token IDs in base tokenizer (use .vocab attribute)
        expected_special = {'PAD_None': 0, 'BOS_None': 1, 'EOS_None': 2, 'MASK_None': 3}
        for name, expected_id in expected_special.items():
            actual_id = self.base_tokenizer.vocab.get(name)
            if actual_id != expected_id:
                raise ValueError(f"Special token {name} has ID {actual_id}, expected {expected_id}")
        
        print("Base tokenizer vocabulary verified: 12000 tokens, special tokens at expected positions")
    
    def __len__(self) -> int:
        return self.VOCAB_SIZE
    
    @property
    def vocab_size(self) -> int:
        return self.VOCAB_SIZE
    
    @property
    def pad_token_id(self) -> int:
        return self.base_tokenizer.vocab['PAD_None']
    
    @property
    def bos_token_id(self) -> int:
        return self.base_tokenizer.vocab['BOS_None']
    
    @property
    def eos_token_id(self) -> int:
        return self.base_tokenizer.vocab['EOS_None']
    
    @property
    def mask_token_id(self) -> int:
        return self.base_tokenizer.vocab['MASK_None']
    
    def token_to_id(self, token: str) -> int:
        """Convert token string to ID."""
        if token in self.special_tokens:
            return self.special_tokens[token]
        return self.base_tokenizer.vocab[token]
    
    def id_to_token(self, token_id: int) -> str:
        """Convert token ID to string."""
        if token_id in self.id_to_special:
            return self.id_to_special[token_id]
        if token_id < 12000:
            # Use the inverse vocab
            return self.base_tokenizer._vocab_base_inv[token_id]
        raise ValueError(f"Unknown token ID: {token_id}")
    
    def encode_track(self, midi_file: MidiFile, track_idx: int) -> List[int]:
        """
        Encode a single track using the base BPE tokenizer.
        
        Args:
            midi_file: MidiFile object
            track_idx: Index of track to encode
            
        Returns:
            List of token IDs (from base 12000 vocab)
        """
        # Create a temporary MIDI with only this track
        temp_midi = MidiFile()
        temp_midi.ticks_per_beat = midi_file.ticks_per_beat
        temp_midi.instruments = [midi_file.instruments[track_idx]]
        temp_midi.time_signature_changes = midi_file.time_signature_changes
        temp_midi.tempo_changes = midi_file.tempo_changes
        
        # Save to temp file and load with symusic for encoding
        import tempfile
        import symusic
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            temp_path = f.name
        temp_midi.dump(temp_path)
        score = symusic.Score(temp_path)
        import os
        os.unlink(temp_path)
        
        # Encode using base tokenizer
        tokens = self.base_tokenizer.encode(score)
        if isinstance(tokens, list) and len(tokens) > 0 and isinstance(tokens[0], TokSequence):
            tokens = tokens[0].ids
        elif isinstance(tokens, TokSequence):
            tokens = tokens.ids
        
        return tokens
    
    def encode_midi(self, midi_path: Union[str, Path]) -> List[int]:
        """
        Encode a multi-track MIDI file into a single token sequence.
        
        Each track is encoded independently and wrapped with Track_Start/Track_End.
        
        Args:
            midi_path: Path to MIDI file
            
        Returns:
            List of token IDs including Track_Start/Track_End markers
        """
        import symusic
        score = symusic.Score(str(midi_path))
        
        # Convert to miditoolkit for track iteration
        midi_file = MidiFile(str(midi_path))
        
        all_tokens = []
        
        # Add BOS
        all_tokens.append(self.bos_token_id)
        
        for track_idx, instrument in enumerate(midi_file.instruments):
            # Skip empty tracks
            if not instrument.notes:
                continue
            
            # Track start marker
            all_tokens.append(self.TRACK_START_ID)
            
            # Track metadata: program and is_drum
            all_tokens.append(self.TRACK_PROGRAM_ID)
            all_tokens.append(instrument.program)
            all_tokens.append(self.TRACK_IS_DRUM_ID)
            all_tokens.append(1 if instrument.is_drum else 0)
            
            # Encode track content
            track_tokens = self.encode_track(midi_file, track_idx)
            all_tokens.extend(track_tokens)
            
            # Track end marker
            all_tokens.append(self.TRACK_END_ID)
        
        # Add EOS
        all_tokens.append(self.eos_token_id)
        
        return all_tokens
    
    def decode_tokens(self, token_ids: List[int]) -> MidiFile:
        """
        Decode token sequence back to multi-track MIDI.
        
        Parses Track_Start/Track_End markers and decodes each track separately.
        
        Args:
            token_ids: List of token IDs
            
        Returns:
            Reconstructed MidiFile with separate tracks
        """
        # Split by track markers and extract metadata
        tracks_data = []  # List of (program, is_drum, track_tokens)
        current_track = []
        current_program = 0
        current_is_drum = False
        in_track = False
        expecting_program = False
        expecting_is_drum = False
        
        i = 0
        while i < len(token_ids):
            tid = token_ids[i]
            if tid == self.TRACK_START_ID:
                if in_track:
                    raise ValueError("Nested Track_Start without Track_End")
                in_track = True
                current_track = []
                current_program = 0
                current_is_drum = False
                parse_state = 0
            elif tid == self.TRACK_END_ID:
                if not in_track:
                    raise ValueError("Track_End without Track_Start")
                in_track = False
                if current_track:
                    tracks_data.append((current_program, current_is_drum, current_track))
            elif tid == self.TRACK_PROGRAM_ID:
                parse_state = 1
            elif tid == self.TRACK_IS_DRUM_ID:
                parse_state = 3
            else:
                if in_track:
                    if parse_state == 0:  # expect TRACK_PROGRAM_ID
                        raise ValueError("Expected TRACK_PROGRAM_ID after TRACK_START_ID, got {}".format(tid))
                    elif parse_state == 1:  # read program number
                        current_program = tid
                        parse_state = 2
                    elif parse_state == 2:  # expect TRACK_IS_DRUM_ID
                        raise ValueError("Expected TRACK_IS_DRUM_ID after program number, got {}".format(tid))
                    elif parse_state == 3:  # read is_drum flag
                        current_is_drum = bool(tid)
                        parse_state = 4
                    elif parse_state == 4:  # read track tokens
                        current_track.append(tid)
                else:
                    if tracks_data:
                        tracks_data[0] = (tracks_data[0][0], tracks_data[0][1], [tid] + tracks_data[0][2])
            i += 1
        
        if in_track:
            raise ValueError("Unclosed Track_Start at end of sequence")
        
        import symusic
        import io
        import tempfile
        import os
        
        midi_file = MidiFile()
        midi_file.ticks_per_beat = 480
        
        for program, is_drum, track_tokens in tracks_data:
            if not track_tokens:
                continue
            full_track_tokens = [self.bos_token_id] + track_tokens + [self.eos_token_id]
            # Pass BPE token IDs directly to base tokenizer decode
            # It handles BPE -> REMI -> MIDI internally
            track_score = self.base_tokenizer.decode(full_track_tokens)
            
            with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
                temp_path = f.name
            track_score.dump_midi(temp_path)
            track_midi = MidiFile(temp_path)
            os.unlink(temp_path)
            
            for inst in track_midi.instruments:
                inst.program = program
                inst.is_drum = is_drum
                midi_file.instruments.append(inst)
            
            if midi_file.ticks_per_beat == 480 and track_midi.ticks_per_beat != 480:
                midi_file.ticks_per_beat = track_midi.ticks_per_beat
            if not midi_file.tempo_changes and track_midi.tempo_changes:
                midi_file.tempo_changes = track_midi.tempo_changes
            if not midi_file.time_signature_changes and track_midi.time_signature_changes:
                midi_file.time_signature_changes = track_midi.time_signature_changes
        
        return midi_file
    
    def _build_complete_vocab(self):
        """Build complete vocabulary including BPE merges from HF tokenizer."""
        # Use the REMI tokenizer's vocab (REMI format: Type_Value)
        # The base_tokenizer.vocab maps REMI token strings to IDs
        remi_vocab = self.base_tokenizer.vocab
        self._complete_voc = {v: k for k, v in remi_vocab.items()}
        print(f"Built complete vocabulary with {len(self._complete_voc)} REMI tokens")
    
    def save_pretrained(self, save_dir: Union[str, Path]):
        """Save MMM v2 tokenizer configuration and vocabulary."""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save base tokenizer config (for reference)
        base_config = self.base_tokenizer.config
        with open(save_dir / "tokenizer_config_base.json", "w") as f:
            json.dump(base_config, f, indent=2)
        
        # Save MMM v2 config
        mmm_config = {
            "model": "MMMv2",
            "base_tokenizer": "MusicTokenizer (BPE)",
            "base_vocab_size": 12000,
            "track_start_id": self.TRACK_START_ID,
            "track_end_id": self.TRACK_END_ID,
            "vocab_size": self.VOCAB_SIZE,
            "special_tokens": {
                "PAD_None": self.pad_token_id,
                "BOS_None": self.bos_token_id,
                "EOS_None": self.eos_token_id,
                "MASK_None": self.mask_token_id,
                "Track_Start": self.TRACK_START_ID,
                "Track_End": self.TRACK_END_ID,
            },
            "base_tokenizer_path": str(self.official_tokenizer_path),
        }
        with open(save_dir / "tokenizer_config_mmm_v2.json", "w") as f:
            json.dump(mmm_config, f, indent=2)
        
        # Save vocabulary mapping (base vocab + new tokens)
        vocab = {}
        # Add base vocab
        for token, tid in self.base_tokenizer.vocab.items():
            vocab[token] = tid
        # Add new special tokens
        vocab["Track_Start"] = self.TRACK_START_ID
        vocab["Track_End"] = self.TRACK_END_ID
        
        tokenizer_json = {
            "model": "MMMv2",
            "vocab": vocab,
        }
        with open(save_dir / "tokenizer.json", "w") as f:
            json.dump(tokenizer_json, f, indent=2)
        
        print(f"MMM v2 tokenizer saved to {save_dir}")
        print(f"  Vocab size: {self.VOCAB_SIZE}")
        print(f"  Base vocab: 12000 (preserved)")
        print(f"  Track_Start: {self.TRACK_START_ID}")
        print(f"  Track_End: {self.TRACK_END_ID}")
    
    @classmethod
    def from_pretrained(cls, save_dir: Union[str, Path]) -> "MMMv2Tokenizer":
        """Load MMM v2 tokenizer from saved directory."""
        save_dir = Path(save_dir)
        config_path = save_dir / "tokenizer_config_mmm_v2.json"
        with open(config_path) as f:
            config = json.load(f)
        
        base_path = config["base_tokenizer_path"]
        return cls(base_path)


def test_mmm_v2():
    """Test MMM v2 tokenizer with a sample MIDI."""
    import tempfile
    
    # Load official tokenizer
    official_path = Path(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-official")
    mmm = MMMv2Tokenizer(official_path)
    
    # Test with a Slakh sample
    slakh_dir = Path(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\datasets\Slakh2100_samples")
    midi_files = list(slakh_dir.rglob("all_src.mid"))
    
    if not midi_files:
        print("No MIDI files found for testing")
        return
    
    test_midi = midi_files[0]
    print(f"\nTesting with: {test_midi}")
    
    # Load original MIDI
    original_midi = MidiFile(test_midi)
    print(f"Original tracks: {len(original_midi.instruments)}")
    for i, inst in enumerate(original_midi.instruments):
        print(f"  Track {i}: program={inst.program}, is_drum={inst.is_drum}, notes={len(inst.notes)}")
    
    # Encode
    token_ids = mmm.encode_midi(test_midi)
    print(f"\nEncoded tokens: {len(token_ids)}")
    print(f"Token range: {min(token_ids)} - {max(token_ids)}")
    
    # Verify all regular tokens are in base vocab range
    regular_tokens = [t for t in token_ids if t < 12000]
    special_tokens = [t for t in token_ids if t >= 12000]
    print(f"Regular tokens (0-11999): {len(regular_tokens)}")
    print(f"Special tokens (>=12000): {special_tokens}")
    
    assert all(0 <= t < 12000 for t in regular_tokens), "Regular tokens out of base vocab range!"
    assert mmm.TRACK_START_ID in token_ids, "Track_Start missing"
    assert mmm.TRACK_END_ID in token_ids, "Track_End missing"
    
    # Count tracks from markers
    track_starts = token_ids.count(mmm.TRACK_START_ID)
    track_ends = token_ids.count(mmm.TRACK_END_ID)
    print(f"Track_Start count: {track_starts}")
    print(f"Track_End count: {track_ends}")
    
    # Decode
    decoded_midi = mmm.decode_tokens(token_ids)
    print(f"\nDecoded tracks: {len(decoded_midi.instruments)}")
    for i, inst in enumerate(decoded_midi.instruments):
        print(f"  Track {i}: program={inst.program}, is_drum={inst.is_drum}, notes={len(inst.notes)}")
    
    # Verify track count preserved
    original_non_empty = sum(1 for inst in original_midi.instruments if inst.notes)
    decoded_non_empty = sum(1 for inst in decoded_midi.instruments if inst.notes)
    print(f"\nOriginal non-empty tracks: {original_non_empty}")
    print(f"Decoded non-empty tracks: {decoded_non_empty}")
    
    assert original_non_empty == decoded_non_empty, f"Track count mismatch: {original_non_empty} != {decoded_non_empty}"
    print("✓ Round-trip track count preserved!")
    
    # Save test output
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        decoded_midi.dump(f.name)
        print(f"Decoded MIDI saved to: {f.name}")
    
    # Save tokenizer
    mmm.save_pretrained(r"C:\Users\migue\.cline\data\workspaces\chat\Mozart\experiments\aura-midi\models\shikhr-music-maker-multitrack-v2")
    
    return mmm


if __name__ == "__main__":
    test_mmm_v2()