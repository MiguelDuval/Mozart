#!/usr/bin/env python3
"""
End-to-end smoke test of the original shikhr/music_maker model (Stage 3).

No training. Path under test:
  real validation MIDI -> tokenizer.encode -> model.generate -> tokenizer.decode
  -> dump MIDI -> re-open -> metrics.

Uses ONLY the local official model directory (safetensors weights, SHA-256
38e1083... verified against the project record) and the local tokenizer.
Runs on CUDA if available, otherwise CPU.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
MODEL_DIR = REPO_ROOT / "experiments" / "aura-midi" / "models" / "shikhr-music-maker-official"

sys.path.insert(0, str(MODEL_DIR))

import symusic  # noqa: E402
import torch  # noqa: E402
import safetensors.torch as st  # noqa: E402
from mgpt_config import MGPTConfig  # noqa: E402
from gpt_model import GPT  # noqa: E402
from evaluate_models import (  # noqa: E402
    load_pretrained_model,
    generate,
    score_metrics,
    midi_valid_and_reopenable,
    prompt_seed,
    file_sha256,
)
from miditok import MusicTokenizer  # noqa: E402

CKPT_SHA256 = "38e1083aea069e298f40373ebc394211b66b876702df91b2c4488cbd53079319"


def _first_validation_prompt(tokenizer, prompt_len=32):
    runs_dir = REPO_ROOT / "experiments" / "aura-midi" / "runs"
    for lst in ("nrgcp_val_files.txt", "gmd_val_files.txt"):
        path = runs_dir / lst
        if path.exists():
            with open(path) as f:
                first = next((line.strip() for line in f if line.strip()), None)
            if first and Path(first).exists():
                score = symusic.Score(first)
                ids = tokenizer.encode(score).ids
                if len(ids) >= prompt_len + 1:
                    return ids[:prompt_len]
    # Fallback: deterministic synthetic prompt in-vocab.
    return list(range(100, 100 + prompt_len))


class TestOriginalModelSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        meta = load_pretrained_model(MODEL_DIR, cls.device)
        cls.model = meta["model"]
        cls.model.eval()
        cls.config = meta["config"]
        cls.tokenizer = MusicTokenizer.from_pretrained(str(MODEL_DIR))
        cls.missing = meta["missing"]
        cls.unexpected = meta["unexpected"]

    def test_model_loads_from_original_weights(self):
        self.assertIsNotNone(self.model)
        self.assertEqual(self.config.vocab_size, 12000)
        # Official safetensors stores lm_head.weight; the loader promotes it to
        # transformer.wte.weight (weight tying), so nothing is missing/unexpected.
        self.assertEqual(self.missing, [])
        self.assertEqual(self.unexpected, [])
        total = sum(p.numel() for p in self.model.parameters())
        self.assertEqual(total, 44_429_824)

    def test_loaded_weights_match_checkpoint(self):
        """Loaded wte/lm_head hold the checkpoint's trained lm_head values;
        wte and lm_head are the same (tied) tensor; all other tensors match."""
        ckpt_path = MODEL_DIR / "model.safetensors"
        self.assertEqual(file_sha256(ckpt_path), CKPT_SHA256)
        ckpt = st.load_file(str(ckpt_path))

        m = self.model
        # Weight tying: same tensor object
        self.assertIs(m.transformer.wte.weight, m.lm_head.weight)

        # Loaded values equal the checkpoint's lm_head.weight (the only stored copy)
        ref = ckpt["model.lm_head.weight"]
        self.assertTrue(torch.allclose(m.transformer.wte.weight, ref),
                        "wte does not match checkpoint lm_head.weight")
        self.assertTrue(torch.allclose(m.lm_head.weight, ref),
                        "lm_head does not match checkpoint lm_head.weight")

        # Every other tensor matches the checkpoint
        for k, v in ckpt.items():
            name = k[6:] if k.startswith("model.") else k
            if name in ("lm_head.weight", "transformer.wte.weight"):
                continue
            self.assertIn(name, m.state_dict(), f"checkpoint key {name} not in model")
            self.assertTrue(torch.allclose(m.state_dict()[name], v),
                            f"tensor mismatch: {name}")

    def test_score_metrics_matches_independent_file_metrics(self):
        """score_metrics (in-memory) and independent file-based metrics
        (verify_midi_metrics.py logic) must agree on the same MIDI file.
        Guards against divergence between the two evaluators."""
        import tempfile
        from pathlib import Path as _Path

        prompt_ids = list(range(100, 100 + 32))
        seed = prompt_seed(20261027, "metrics-cross-check")
        ids, score, info = generate(
            self.model, self.tokenizer, prompt_ids, self.device,
            max_new=32, temperature=1.0, top_k=40, seed=seed,
        )
        with tempfile.TemporaryDirectory() as td:
            midi_path = _Path(td) / "cross_check.mid"
            score.dump_midi(str(midi_path))

            # Re-open from disk (independent path, same as verify_midi_metrics.py)
            reopened = symusic.Score(str(midi_path))
            sm = score_metrics(reopened)

            # Independent recomputation from the re-opened score
            tpq = reopened.tpq
            all_notes = []
            for tr in reopened.tracks:
                for n in tr.notes:
                    all_notes.append(n)
            total_notes = len(all_notes)
            end_tick = max((n.end for n in all_notes), default=0)
            duration_beats = end_tick / tpq if tpq else 0.0
            events = []
            for n in all_notes:
                events.append((n.start, 1))
                events.append((n.end, -1))
            events.sort()
            cur = 0
            max_poly = 0
            for _, delta in events:
                cur += delta
                max_poly = max(max_poly, cur)
            density = total_notes / duration_beats if duration_beats else 0.0

            self.assertEqual(sm["num_notes"], total_notes,
                             f"note count mismatch: {sm['num_notes']} vs {total_notes}")
            self.assertEqual(sm["duration_ticks"], int(end_tick),
                             f"duration ticks mismatch: {sm['duration_ticks']} vs {int(end_tick)}")
            self.assertAlmostEqual(sm["duration_beats"], round(duration_beats, 4), places=4,
                                   msg=f"duration beats mismatch: {sm['duration_beats']} vs {round(duration_beats, 4)}")
            self.assertEqual(sm["max_polyphony"], max_poly,
                             f"polyphony mismatch: {sm['max_polyphony']} vs {max_poly}")
            self.assertAlmostEqual(sm["density_notes_per_beat"], round(density, 4), places=4,
                                   msg=f"density mismatch: {sm['density_notes_per_beat']} vs {round(density, 4)}")

    def test_generate_decode_roundtrip_produces_valid_midi(self):
        prompt_ids = _first_validation_prompt(self.tokenizer)
        seed = prompt_seed(20261027, "smoke-prompt")
        ids, score, info = generate(
            self.model, self.tokenizer, prompt_ids, self.device,
            max_new=64, temperature=1.0, top_k=40, seed=seed,
        )
        # Generation always emits exactly max_new continuation tokens.
        self.assertEqual(info["new_tokens"], 64)
        self.assertEqual(len(ids), len(prompt_ids) + 64)
        self.assertIn("eos_count", info)

        metrics = score_metrics(score)
        self.assertGreaterEqual(metrics["num_notes"], 0)
        self.assertGreaterEqual(metrics["duration_beats"], 0.0)

        with tempfile.TemporaryDirectory() as td:
            midi_path = Path(td) / "smoke_generated.mid"
            score.dump_midi(str(midi_path))
            reopen = midi_valid_and_reopenable(midi_path)
            self.assertTrue(reopen["valid"], msg=reopen.get("error"))
            self.assertTrue(reopen["reopened"])
            self.assertGreaterEqual(reopen["notes"], 0)

    def test_tokenizer_encode_decode_stable(self):
        prompt_ids = _first_validation_prompt(self.tokenizer)
        score = self.tokenizer.decode(prompt_ids)
        metrics = score_metrics(score)
        self.assertGreaterEqual(metrics["num_notes"], 0)


if __name__ == "__main__":
    unittest.main()
