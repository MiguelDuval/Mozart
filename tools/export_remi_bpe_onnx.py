#!/usr/bin/env python3
"""Export a local MidiTok REMI/BPE checkpoint to a separate experimental ONNX ABI.

This does not export Mozart's frozen 512-token model. The source directory must
already contain the model and its paired MidiTok tokenizer; no checkpoint is
downloaded and no model artifact is written into the repository tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPECIAL_NAMES = ("PAD_None", "BOS_None", "EOS_None", "MASK_None")
MAX_VOCAB_SIZE = 2_000_000


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_miditok_tokenizer(path: Path) -> dict[str, Any]:
    """Read the outer MidiTok config and embedded HF BPE vocabulary strictly."""
    payload = _read_json(path)
    if payload.get("tokenization") != "REMI":
        raise ValueError("tokenizer must declare tokenization='REMI'")

    outer_config = payload.get("config")
    if not isinstance(outer_config, dict):
        raise ValueError("MidiTok tokenizer is missing config")
    byte_to_token = payload.get("_vocab_base_byte_to_token")
    if not isinstance(byte_to_token, dict) or not byte_to_token:
        raise ValueError("MidiTok tokenizer is missing _vocab_base_byte_to_token")

    raw_model = payload.get("_model")
    if not isinstance(raw_model, str):
        raise ValueError("MidiTok tokenizer is missing the serialized _model")
    try:
        model_payload = json.loads(
            raw_model, object_pairs_hook=_reject_duplicate_json_keys
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot parse MidiTok embedded BPE model: {exc}") from exc

    model = model_payload.get("model") if isinstance(model_payload, dict) else None
    if not isinstance(model, dict) or model.get("type") != "BPE":
        raise ValueError("expected a MidiTok tokenizer backed by a BPE model")
    vocab = model.get("vocab")
    if not isinstance(vocab, dict) or not vocab:
        raise ValueError("embedded BPE model vocabulary is missing")

    ids: list[int] = []
    for token, token_id in vocab.items():
        if not isinstance(token, str) or isinstance(token_id, bool) or not isinstance(token_id, int):
            raise ValueError("embedded BPE vocabulary must map token strings to integer IDs")
        if token_id < 0 or token_id >= MAX_VOCAB_SIZE:
            raise ValueError(f"embedded BPE token ID is outside supported bounds: {token_id}")
        ids.append(token_id)
    if len(ids) != len(set(ids)):
        raise ValueError("embedded BPE vocabulary contains duplicate token IDs")
    vocab_size = len(vocab)
    if sorted(ids) != list(range(vocab_size)):
        raise ValueError("embedded BPE vocabulary IDs must be contiguous from zero")

    # Resolve special tokens through MidiTok's stored byte -> semantic-token
    # mapping and the BPE model's *actual* IDs; never infer them from list order.
    encoded_to_id = {encoded: token_id for encoded, token_id in vocab.items()}
    special_ids: dict[str, int] = {}
    for encoded, semantic_name in byte_to_token.items():
        if semantic_name in SPECIAL_NAMES and encoded in encoded_to_id:
            if semantic_name in special_ids:
                raise ValueError(f"multiple BPE byte entries map to {semantic_name}")
            special_ids[semantic_name] = encoded_to_id[encoded]
    missing = [name for name in SPECIAL_NAMES[:3] if name not in special_ids]
    if missing:
        raise ValueError("tokenizer does not resolve required special tokens: " + ", ".join(missing))

    tokenizer_config = {
        "pitch_range": outer_config.get("pitch_range"),
        "beat_res": outer_config.get("beat_res"),
        "num_velocities": outer_config.get("num_velocities"),
        "default_note_duration": outer_config.get("default_note_duration"),
        "num_tempos": outer_config.get("num_tempos"),
        "tempo_range": outer_config.get("tempo_range"),
        "use_tempos": outer_config.get("use_tempos"),
        "use_time_signatures": outer_config.get("use_time_signatures"),
        "use_programs": outer_config.get("use_programs"),
    }

    return {
        "tokenization": "REMI",
        "vocab_size": vocab_size,
        "special_token_ids": special_ids,
        "tokenizer_sha256": sha256_file(path),
        "config": tokenizer_config,
    }


def inspect_model_architecture(
    model_config: dict[str, Any],
    tokenizer_vocab_size: int,
    *,
    trust_model_code: bool,
) -> dict[str, Any]:
    """Validate a supported causal-LM architecture against its paired tokenizer.

    MusicMaker's custom mgpt architecture requires explicitly reviewed local
    code. Standard GPT-2 checkpoints use Transformers' built-in causal-LM class
    with remote/custom code execution disabled.
    """
    model_type = model_config.get("model_type")
    if model_type not in {"mgpt", "gpt2"}:
        raise ValueError(
            "supported REMI/BPE model_type values are 'mgpt' and 'gpt2'; "
            f"found {model_type!r}"
        )

    declared_vocab = model_config.get("vocab_size")
    if (
        isinstance(declared_vocab, bool)
        or not isinstance(declared_vocab, int)
        or declared_vocab <= 0
    ):
        raise ValueError("model config vocab_size must be a positive integer")
    if declared_vocab != tokenizer_vocab_size:
        raise ValueError(
            f"model config vocab_size ({declared_vocab}) does not match tokenizer "
            f"({tokenizer_vocab_size})"
        )

    architectures = model_config.get("architectures")
    if model_type == "gpt2":
        if architectures is not None and (
            not isinstance(architectures, list)
            or "GPT2LMHeadModel" not in architectures
        ):
            raise ValueError(
                "gpt2 REMI/BPE export requires a GPT2LMHeadModel causal-language-model head"
            )
        return {
            "model_type": "gpt2",
            "loader": "AutoModelForCausalLM",
            "trust_remote_code": False,
            "architecture_class": "GPT2LMHeadModel",
        }

    if not trust_model_code:
        raise ValueError(
            "MusicMaker mgpt requires reviewed local custom model code; "
            "pass --trust-model-code only after reviewing it"
        )
    return {
        "model_type": "mgpt",
        "loader": "AutoModel",
        "trust_remote_code": True,
        "architecture_class": (
            architectures[0]
            if isinstance(architectures, list) and architectures
            else "MusicMaker mgpt"
        ),
    }


def _context_length(config: dict[str, Any]) -> int:
    for name in ("block_size", "max_position_embeddings", "n_positions", "max_sequence_length"):
        value = config.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value > 1:
            return value
    raise ValueError("model config does not declare a supported context length")


def _disable_flash_attention(model: Any) -> None:
    # The upstream nanoGPT-style model selects SDPA when available. The portable
    # ONNX export uses its explicit causal-mask implementation instead.
    for module in model.modules():
        if hasattr(module, "flash"):
            module.flash = False


def _extract_logits(output: Any) -> Any:
    if hasattr(output, "logits"):
        logits = output.logits
    elif isinstance(output, (tuple, list)):
        if not output:
            raise ValueError("model returned an empty output tuple")
        logits = output[0]
    else:
        logits = output
    if not hasattr(logits, "ndim") or logits.ndim != 3:
        raise ValueError("model forward must return rank-3 logits [batch, sequence, vocab]")
    return logits


def export_loaded_model(
    model: Any,
    tokenizer_contract: dict[str, Any],
    output_path: Path,
    *,
    context_length: int,
    sample_sequence_length: int = 8,
    max_generated_tokens: int = 400,
    opset: int = 17,
) -> dict[str, Any]:
    """Export a loaded causal LM and compare eager/ONNX logits at several lengths."""
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    from torch import nn

    vocab_size = tokenizer_contract["vocab_size"]
    special_ids = tokenizer_contract["special_token_ids"]
    if getattr(getattr(model, "config", None), "vocab_size", None) != vocab_size:
        raise ValueError(
            "model config vocab_size does not match the actual MidiTok BPE vocabulary "
            f"({getattr(getattr(model, 'config', None), 'vocab_size', None)} != {vocab_size})"
        )
    if sample_sequence_length < 1 or sample_sequence_length > context_length:
        raise ValueError("sample sequence length must be within the model context")
    if max_generated_tokens < 2 or max_generated_tokens > context_length:
        raise ValueError("max generated tokens must be in [2, context_length]")
    if opset < 17:
        raise ValueError("ONNX opset must be at least 17")

    class LastTokenLogits(nn.Module):
        def __init__(self, inner: Any) -> None:
            super().__init__()
            self.inner = inner

        def forward(self, input_ids: Any) -> Any:
            logits = _extract_logits(self.inner(input_ids))
            return logits[:, -1, :]

    _disable_flash_attention(model)
    model.eval()
    wrapper = LastTokenLogits(model).eval()
    pad_id = special_ids["PAD_None"]
    bos_id = special_ids["BOS_None"]
    sample = torch.full((1, sample_sequence_length), pad_id, dtype=torch.long)
    sample[0, 0] = bos_id

    with torch.no_grad():
        eager = wrapper(sample)
    if tuple(eager.shape) != (1, vocab_size):
        raise ValueError(
            f"unexpected eager output shape {tuple(eager.shape)}; expected (1, {vocab_size})"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        wrapper,
        (sample,),
        str(output_path),
        input_names=["input_ids"],
        output_names=["logits"],
        dynamic_axes={"input_ids": {1: "sequence"}},
        opset_version=opset,
        do_constant_folding=True,
        dynamo=False,
    )
    onnx.checker.check_model(str(output_path))

    session = ort.InferenceSession(
        str(output_path), providers=["CPUExecutionProvider"]
    )
    input_meta = session.get_inputs()
    output_meta = session.get_outputs()
    if len(input_meta) != 1 or input_meta[0].name != "input_ids" or input_meta[0].type != "tensor(int64)":
        raise ValueError("exported ONNX graph does not expose the required int64 input_ids tensor")
    if len(output_meta) != 1 or output_meta[0].name != "logits" or output_meta[0].type != "tensor(float)":
        raise ValueError("exported ONNX graph does not expose the required float logits tensor")

    tested_lengths = sorted({1, min(2, context_length), sample_sequence_length})
    for length in tested_lengths:
        ids = torch.full((1, length), pad_id, dtype=torch.long)
        ids[0, 0] = bos_id
        with torch.no_grad():
            expected = wrapper(ids).cpu().numpy()
        actual = session.run(["logits"], {"input_ids": ids.cpu().numpy()})[0]
        if actual.shape != (1, vocab_size):
            raise ValueError(f"ONNX output shape {actual.shape} is not (1, {vocab_size})")
        np.testing.assert_allclose(actual, expected, rtol=2e-3, atol=2e-3)
    return {
        "vocabulary_size": vocab_size,
        "context_length_tokens": context_length,
        "max_generated_tokens": max_generated_tokens,
        "tested_sequence_lengths": tested_lengths,
        "input_shape": [1, -1],
        "output_shape": [1, vocab_size],
    }


def build_manifest(
    *,
    model_id: str,
    model_revision: str,
    model_file: str,
    model_sha256: str,
    tokenizer_file: str,
    tokenizer_contract: dict[str, Any],
    context_length: int,
    max_generated_tokens: int,
    source_code_files_sha256: dict[str, str],
    source_checkpoint_files_sha256: dict[str, str],
) -> dict[str, Any]:
    vocab_size = tokenizer_contract["vocab_size"]
    special_ids = tokenizer_contract["special_token_ids"]
    return {
        "manifest_schema_version": 1,
        "manifest_status": "frozen",
        "model_id": model_id,
        "model_revision": model_revision,
        "model_file": model_file,
        "model_format": "onnx",
        "model_sha256": model_sha256,
        "distribution_class": "private_experimental",
        "vocabulary_id": "miditok-remi-bpe-v1",
        "vocabulary_size": vocab_size,
        "context_length_tokens": context_length,
        "max_generated_tokens": max_generated_tokens,
        "inputs": [
            {
                "name": "input_ids",
                "dtype": "int64",
                "shape": [1, -1],
                "layout": "batch_sequence",
                "role": "remi_bpe_token_ids",
            }
        ],
        "outputs": [
            {
                "name": "logits",
                "dtype": "float32",
                "shape": [1, vocab_size],
                "layout": "batch_vocabulary",
                "role": "next_token_logits",
            }
        ],
        "kv_cache": {"enabled": False, "tensors": []},
        "quantization": {
            "scheme": "none",
            "activations": "float32",
            "weights": "float32",
            "scales": "not_applicable",
            "zero_points": "not_applicable",
        },
        "conditioning": {
            "style_family": "not_supported_by_unconditional_piano_checkpoint",
            "substyle": "not_supported_by_unconditional_piano_checkpoint",
            "mood": "not_supported_by_unconditional_piano_checkpoint",
            "rhythm": "not_supported_by_unconditional_piano_checkpoint",
            "role": "single_piano_track",
            "key_scale": "not_conditioned",
            "chords": "not_conditioned",
            "density": "not_conditioned",
            "energy": "not_conditioned",
            "syncopation": "not_conditioned",
            "swing": "not_conditioned",
            "variation": "not_conditioned",
            "seed": "unused_with_greedy_argmax",
        },
        "decoding": {
            "strategy": "greedy_argmax",
            "temperature": 0.0,
            "top_k": 1,
            "top_p": 1.0,
            "seed_policy": "unused_with_greedy_argmax",
        },
        "provenance": {
            "training_source": "adl-piano-midi as described by the upstream model card; source inventory requires separate audit",
            "dataset_manifest": "not provided by the upstream checkpoint; rights/provenance review required",
            "preprocessing_revision": "MidiTok tokenizer SHA-256 recorded in this manifest",
        },
        "licenses": {
            "implementation": "upstream model card states MIT; verify checked-out model code files before redistribution",
            "model_weights": "private external checkpoint; redistribution review required",
            "training_data": "upstream card describes adl-piano-midi; dataset rights remain to be audited",
            "redistribution": "private experimental use only pending provenance and license review",
        },
        "runtime": {
            "backend": "onnxruntime",
            "input_name": "input_ids",
            "output_name": "logits",
            "input_dtype": "int64",
            "token_mode": "remi_bpe",
            "external_vocabulary_size": vocab_size,
            "context_length_tokens": context_length,
            "max_generated_tokens": max_generated_tokens,
            "pad_token_id": special_ids["PAD_None"],
            "bos_token_id": special_ids["BOS_None"],
            "eos_token_id": special_ids["EOS_None"],
            "mask_token_id": special_ids.get("MASK_None"),
            "tokenizer_file": tokenizer_file,
            "tokenizer_sha256": tokenizer_contract["tokenizer_sha256"],
            "allow_unhashed_experimental": False,
        },
        "source_code_files_sha256": source_code_files_sha256,
        "source_checkpoint_files_sha256": source_checkpoint_files_sha256,
    }


def _hash_files(model_dir: Path, patterns: tuple[str, ...]) -> dict[str, str]:
    files: dict[str, str] = {}
    for pattern in patterns:
        for path in sorted(model_dir.glob(pattern)):
            if path.is_file():
                files[path.name] = sha256_file(path)
    return files


def export_local_model(
    model_dir: Path,
    output_path: Path,
    manifest_path: Path,
    *,
    model_id: str,
    model_revision: str,
    sample_sequence_length: int,
    max_generated_tokens: int,
    opset: int,
    trust_model_code: bool,
) -> dict[str, Any]:
    model_dir = model_dir.resolve()
    output_path = output_path.resolve()
    manifest_path = manifest_path.resolve()
    if not model_dir.is_dir():
        raise ValueError(f"model directory does not exist: {model_dir}")
    if output_path == manifest_path or output_path.parent != manifest_path.parent:
        raise ValueError("model and manifest must be separate files in the same output directory")
    if output_path.suffix.lower() != ".onnx" or manifest_path.suffix.lower() != ".json":
        raise ValueError("output must end in .onnx and manifest must end in .json")
    if output_path.is_relative_to(ROOT) or manifest_path.is_relative_to(ROOT):
        raise ValueError(
            "model exports are large private artifacts; choose an output directory outside the repository"
        )

    config_path = model_dir / "config.json"
    tokenizer_path = model_dir / "tokenizer.json"
    if not config_path.is_file() or not tokenizer_path.is_file():
        raise ValueError("model directory must contain config.json and tokenizer.json")
    weight_candidates = (
        model_dir / "model.safetensors",
        model_dir / "pytorch_model.bin",
        model_dir / "model.safetensors.index.json",
        model_dir / "pytorch_model.bin.index.json",
    )
    if not any(path.is_file() for path in weight_candidates):
        raise ValueError("model directory does not contain recognized model weights")

    model_config = _read_json(config_path)
    tokenizer_contract = inspect_miditok_tokenizer(tokenizer_path)
    vocab_size = tokenizer_contract["vocab_size"]
    architecture = inspect_model_architecture(
        model_config,
        vocab_size,
        trust_model_code=trust_model_code,
    )
    context_length = _context_length(model_config)
    if sample_sequence_length < 1 or sample_sequence_length > context_length:
        raise ValueError("sample sequence length is outside model context")
    if max_generated_tokens < 2 or max_generated_tokens > context_length:
        raise ValueError("max generated tokens is outside model context")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", model_revision):
        raise ValueError("--model-revision must be a full immutable 40-character commit SHA")
    if model_id is None or not model_id.strip():
        model_id = model_dir.name

    try:
        import torch
        import transformers
        from transformers import AutoModel, AutoModelForCausalLM
    except ImportError as exc:
        raise RuntimeError(
            "missing export dependencies; install tools/requirements-remi-onnx-export.txt"
        ) from exc

    if architecture["loader"] == "AutoModelForCausalLM":
        model = AutoModelForCausalLM.from_pretrained(
            str(model_dir),
            local_files_only=True,
            trust_remote_code=False,
        )
    else:
        model = AutoModel.from_pretrained(
            str(model_dir),
            local_files_only=True,
            trust_remote_code=True,
        )
    loaded_config = getattr(model, "config", None)
    if loaded_config is None or getattr(loaded_config, "model_type", None) != architecture["model_type"]:
        raise ValueError("loaded model architecture differs from config.json")
    if getattr(loaded_config, "vocab_size", None) != vocab_size:
        raise ValueError("loaded checkpoint vocabulary size disagrees with tokenizer")

    export_report = export_loaded_model(
        model,
        tokenizer_contract,
        output_path,
        context_length=context_length,
        sample_sequence_length=sample_sequence_length,
        max_generated_tokens=max_generated_tokens,
        opset=opset,
    )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paired_tokenizer = manifest_path.parent / "tokenizer.json"
    if tokenizer_path.resolve() != paired_tokenizer.resolve():
        shutil.copy2(tokenizer_path, paired_tokenizer)
    # Check the copied tokenizer rather than assuming copy success preserved bytes.
    paired_contract = inspect_miditok_tokenizer(paired_tokenizer)
    if paired_contract["tokenizer_sha256"] != tokenizer_contract["tokenizer_sha256"]:
        raise ValueError("paired tokenizer copy SHA-256 differs from source tokenizer")

    if architecture["model_type"] == "mgpt":
        code_hashes = _hash_files(model_dir, ("*.py",))
        if not code_hashes:
            raise ValueError("MusicMaker mgpt directory contains no local Python model code to audit")
    else:
        import inspect

        source_file = inspect.getsourcefile(type(model))
        if not source_file or not Path(source_file).is_file():
            raise ValueError("cannot identify installed Transformers source for GPT-2 model class")
        source_path = Path(source_file).resolve()
        transformers_root = Path(transformers.__file__).resolve().parent
        try:
            relative_source = source_path.relative_to(transformers_root).as_posix()
        except ValueError as exc:
            raise ValueError("GPT-2 model class source is outside the Transformers package") from exc
        code_hashes = {
            f"transformers/{relative_source}": sha256_file(source_path)
        }

    source_weight_hashes = _hash_files(
        model_dir,
        ("*.safetensors", "*.safetensors.index.json", "pytorch_model*.bin", "pytorch_model*.bin.index.json"),
    )
    manifest = build_manifest(
        model_id=model_id,
        model_revision=model_revision,
        model_file=output_path.name,
        model_sha256=sha256_file(output_path),
        tokenizer_file=paired_tokenizer.name,
        tokenizer_contract=paired_contract,
        context_length=context_length,
        max_generated_tokens=max_generated_tokens,
        source_code_files_sha256=code_hashes,
        source_checkpoint_files_sha256=source_weight_hashes,
    )
    manifest["model_architecture"] = architecture["architecture_class"]
    manifest["transformers_version"] = transformers.__version__
    manifest["loader_class"] = architecture["loader"]
    manifest["source_config_sha256"] = sha256_file(config_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"manifest": manifest, "export_report": export_report, "manifest_path": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True,
                        help="local, reviewed upstream checkpoint directory; no download occurs")
    parser.add_argument("--output", type=Path, required=True,
                        help="ONNX output path outside the repository")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="manifest output path beside the ONNX file")
    parser.add_argument("--model-id", default=None,\n                        help="manifest model identifier; defaults to the local model directory name")
    parser.add_argument("--model-revision", required=True,
                        help="immutable upstream Git/Hugging Face revision")
    parser.add_argument("--sample-sequence-length", type=int, default=8)
    parser.add_argument("--max-generated-tokens", type=int, default=400)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--trust-model-code", action="store_true",
                        help="explicitly allow reviewed local custom model Python to execute")
    args = parser.parse_args()

    try:
        result = export_local_model(
            args.model_dir,
            args.output,
            args.manifest,
            model_id=args.model_id,
            model_revision=args.model_revision,
            sample_sequence_length=args.sample_sequence_length,
            max_generated_tokens=args.max_generated_tokens,
            opset=args.opset,
            trust_model_code=args.trust_model_code,
        )
    except (OSError, ValueError, RuntimeError, ImportError, AssertionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "PASS: exported separate REMI/BPE ONNX graph "
        f"vocab={result['manifest']['vocabulary_size']} "
        f"context={result['manifest']['context_length_tokens']} "
        f"verified_lengths={result['export_report']['tested_sequence_lengths']} "
        f"model={result['manifest']['model_file']} "
        f"manifest={result['manifest_path']}"
    )
    print("NOTE: this export is an experimental unconditioned piano model, not Mozart's 512-token ABI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
