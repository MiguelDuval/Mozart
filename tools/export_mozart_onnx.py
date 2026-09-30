#!/usr/bin/env python3
"""Export the development Mozart Transformer baseline to ONNX.

The emitted graph is experimental. Its tensor names and shapes are facts about
this exact baseline export, not a production ABI for future model revisions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from mozart_model import ModelConfig, MozartTransformer


CONDITIONING_NAMES = (
    "style_id",
    "substyle_id",
    "mood_id",
    "rhythm_id",
    "role_id",
)


def load_checkpoint(model: MozartTransformer, checkpoint_path: Path) -> None:
    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=False,
    )
    state = checkpoint.get("model_state")
    if not isinstance(state, dict):
        raise ValueError("checkpoint does not contain model_state")
    model.load_state_dict(state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("docs/model-training-config.json"),
    )
    parser.add_argument("--sequence-length", type=int, default=16)
    parser.add_argument("--opset", type=int, default=18)
    args = parser.parse_args()

    config = ModelConfig.from_json(args.config)
    if args.sequence_length < 2:
        raise ValueError("--sequence-length must be at least 2")
    if args.sequence_length > config.max_sequence_length:
        raise ValueError("--sequence-length exceeds configured model context")
    if args.opset < 17:
        raise ValueError("--opset must be at least 17")

    model = MozartTransformer(config)
    load_checkpoint(model, args.checkpoint)
    model.eval()

    input_ids = torch.ones(
        (1, args.sequence_length),
        dtype=torch.long,
    )
    condition_ids = tuple(
        torch.zeros(1, dtype=torch.long)
        for _ in CONDITIONING_NAMES
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sequence_dim = torch.export.Dim(
        "sequence",
        min=2,
        max=config.max_sequence_length,
    )
    dynamic_shapes = {
        "input_ids": {1: sequence_dim},
        "style_id": {},
        "substyle_id": {},
        "mood_id": {},
        "rhythm_id": {},
        "role_id": {},
    }
    onnx_program = torch.onnx.export(
        model,
        (input_ids, *condition_ids),
        input_names=("input_ids", *CONDITIONING_NAMES),
        output_names=("logits",),
        dynamic_shapes=dynamic_shapes,
        opset_version=args.opset,
        dynamo=True,
    )
    if onnx_program is None:
        raise RuntimeError("ONNX exporter did not return a program")
    onnx_program.save(args.output)

    parameter_count = sum(
        parameter.numel() for parameter in model.parameters()
    )
    if parameter_count != 32817024:
        raise ValueError(
            "model parameter count does not match the configured baseline: "
            f"{parameter_count}"
        )
    print(
        f"PASS: exported {config.model_id} "
        f"parameters={parameter_count} "
        f"inputs={1 + len(CONDITIONING_NAMES)} "
        f"output=logits -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
