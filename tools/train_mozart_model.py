#!/usr/bin/env python3
"""Train the Mozart symbolic Transformer baseline from JSONL records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mozart_model import ModelConfig, MozartTransformer, conditioning_ids


PAD = 0


class TokenRecordDataset(Dataset[dict]):
    def __init__(self, path: Path, max_sequence_length: int) -> None:
        self.records: list[dict] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                tokens = record.get("tokens")
                if not isinstance(tokens, list) or len(tokens) < 2:
                    raise ValueError(
                        f"{path}:{line_number}: tokens must contain at least 2 ids"
                    )
                tokens = [int(token) for token in tokens[:max_sequence_length]]
                if len(tokens) < 2:
                    continue
                conditioning = conditioning_ids(record)
                self.records.append({
                    "tokens": tokens,
                    "conditioning": conditioning,
                })

        if not self.records:
            raise ValueError(f"{path}: no usable training records")

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict:
        return self.records[index]


def collate_records(
    records: list[dict],
    max_sequence_length: int,
) -> dict[str, torch.Tensor]:
    max_length = min(
        max(len(record["tokens"]) - 1 for record in records),
        max_sequence_length - 1,
    )
    batch_size = len(records)

    input_ids = torch.full(
        (batch_size, max_length),
        PAD,
        dtype=torch.long,
    )
    targets = torch.full(
        (batch_size, max_length),
        -100,
        dtype=torch.long,
    )
    padding_mask = torch.ones(
        (batch_size, max_length),
        dtype=torch.bool,
    )

    condition = {
        name: torch.zeros(batch_size, dtype=torch.long)
        for name in ("style", "substyle", "mood", "rhythm", "role")
    }

    for row, record in enumerate(records):
        tokens = record["tokens"]
        length = min(len(tokens) - 1, max_length)
        input_ids[row, :length] = torch.tensor(tokens[:length])
        targets[row, :length] = torch.tensor(tokens[1:length + 1])
        padding_mask[row, :length] = False
        for name, value in record["conditioning"].items():
            condition[name][row] = value

    return {
        "input_ids": input_ids,
        "targets": targets,
        "padding_mask": padding_mask,
        **{f"{name}_id": value for name, value in condition.items()},
    }


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def run_epoch(
    model: MozartTransformer,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer | None,
    device: torch.device,
) -> float:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    batches = 0

    for batch in loader:
        input_ids = batch["input_ids"].to(device)
        targets = batch["targets"].to(device)
        padding_mask = batch["padding_mask"].to(device)

        logits = model(
            input_ids,
            batch["style_id"].to(device),
            batch["substyle_id"].to(device),
            batch["mood_id"].to(device),
            batch["rhythm_id"].to(device),
            batch["role_id"].to(device),
            padding_mask=padding_mask,
        )
        loss = criterion(
            logits.reshape(-1, logits.size(-1)),
            targets.reshape(-1),
        )

        if training:
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        total_loss += float(loss.detach().cpu())
        batches += 1

    return total_loss / max(1, batches)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train_jsonl", type=Path)
    parser.add_argument("--validation-jsonl", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("docs/model-training-config.json"),
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
    )
    parser.add_argument("--num-workers", type=int, default=0)
    args = parser.parse_args()

    if args.epochs <= 0 or args.batch_size <= 0:
        raise ValueError("epochs and batch-size must be positive")
    if args.learning_rate <= 0.0:
        raise ValueError("learning-rate must be positive")
    if args.num_workers < 0:
        raise ValueError("num-workers must not be negative")

    set_seed(args.seed)
    config = ModelConfig.from_json(args.config)

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    device = (
        torch.device("cuda")
        if args.device == "cuda"
        else torch.device("cpu")
        if args.device == "cpu"
        else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )

    train_dataset = TokenRecordDataset(
        args.train_jsonl,
        config.max_sequence_length,
    )
    validation_dataset = (
        TokenRecordDataset(args.validation_jsonl, config.max_sequence_length)
        if args.validation_jsonl is not None
        else None
    )

    def collate(records: list[dict]) -> dict[str, torch.Tensor]:
        return collate_records(records, config.max_sequence_length)

    generator = torch.Generator()
    generator.manual_seed(args.seed)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate,
        num_workers=args.num_workers,
        generator=generator,
    )
    validation_loader = (
        DataLoader(
            validation_dataset,
            batch_size=args.batch_size,
            shuffle=False,
            collate_fn=collate,
            num_workers=args.num_workers,
        )
        if validation_dataset is not None
        else None
    )

    model = MozartTransformer(config).to(device)
    criterion = nn.CrossEntropyLoss(ignore_index=-100)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=0.01,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    best_validation = float("inf")

    parameter_count = sum(
        parameter.numel() for parameter in model.parameters()
    )
    print(
        f"MODEL {config.model_id} "
        f"parameters={parameter_count} "
        f"device={device}"
    )

    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device,
        )
        validation_loss = None
        if validation_loader is not None:
            with torch.no_grad():
                validation_loss = run_epoch(
                    model,
                    validation_loader,
                    criterion,
                    None,
                    device,
                )

        message = f"epoch={epoch} train_loss={train_loss:.6f}"
        if validation_loss is not None:
            message += f" validation_loss={validation_loss:.6f}"
        print(message)

        score = validation_loss if validation_loss is not None else train_loss
        checkpoint = {
            "model_id": config.model_id,
            "config": config.__dict__,
            "epoch": epoch,
            "seed": args.seed,
            "train_loss": train_loss,
            "validation_loss": validation_loss,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
        }
        torch.save(checkpoint, args.output_dir / "latest.pt")
        if score < best_validation:
            best_validation = score
            torch.save(checkpoint, args.output_dir / "best.pt")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
