#!/usr/bin/env python3
"""Development baseline architecture for Mozart symbolic MIDI training."""

# Training/export executes in the dedicated ML workflow; Android builds consume contracts only.

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import torch
from torch import Tensor, nn


STYLE_IDS = {
    "electronic": 0,
    "techno": 1,
    "dark_techno": 2,
    "hard_techno": 3,
    "trap": 4,
    "custom": 5,
}
SUBSTYLE_IDS = {
    "generic": 0,
    "techno": 1,
    "dark_techno": 2,
    "hard_techno": 3,
    "trap": 4,
    "dark_trap": 5,
    "custom": 6,
}
MOOD_IDS = {
    "neutral": 0,
    "driving": 1,
    "dark": 2,
    "aggressive": 3,
    "hypnotic": 4,
    "tense": 5,
    "atmospheric": 6,
    "custom": 7,
}
RHYTHM_IDS = {
    "straight": 0,
    "syncopated": 1,
    "swing": 2,
    "half_time": 3,
    "double_time": 4,
    "broken": 5,
    "custom": 6,
}
ROLE_IDS = {
    "bass": 0,
    "arpeggio": 1,
    "chords": 2,
    "lead": 3,
    "drums": 4,
    "percussion": 5,
    "texture": 6,
    "custom": 7,
}


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    vocabulary_id: str
    vocabulary_size: int
    max_sequence_length: int
    d_model: int
    nhead: int
    num_layers: int
    dim_feedforward: int
    dropout: float
    tie_token_embeddings: bool
    conditioning_sizes: dict[str, int]

    @classmethod
    def from_json(cls, path: Path) -> "ModelConfig":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            model_id=payload["model_id"],
            vocabulary_id=payload["vocabulary_id"],
            vocabulary_size=payload["vocabulary_size"],
            max_sequence_length=payload["max_sequence_length"],
            d_model=payload["d_model"],
            nhead=payload["nhead"],
            num_layers=payload["num_layers"],
            dim_feedforward=payload["dim_feedforward"],
            dropout=payload["dropout"],
            tie_token_embeddings=payload["tie_token_embeddings"],
            conditioning_sizes=dict(payload["conditioning"]),
        )


def conditioning_ids(record: dict) -> dict[str, int]:
    conditioning = record.get("conditioning", {})
    values = {
        "style": STYLE_IDS,
        "substyle": SUBSTYLE_IDS,
        "mood": MOOD_IDS,
        "rhythm": RHYTHM_IDS,
        "role": ROLE_IDS,
    }
    result: dict[str, int] = {}
    for name, mapping in values.items():
        value = conditioning.get(name)
        if value not in mapping:
            raise ValueError(f"unsupported conditioning.{name}: {value!r}")
        result[name] = mapping[value]
    return result


class MozartTransformer(nn.Module):
    """Causal Transformer baseline for the frozen Mozart event vocabulary."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        if config.d_model % config.nhead:
            raise ValueError("d_model must be divisible by nhead")

        self.config = config
        self.token_embedding = nn.Embedding(
            config.vocabulary_size, config.d_model
        )
        self.position_embedding = nn.Embedding(
            config.max_sequence_length, config.d_model
        )

        self.condition_embeddings = nn.ModuleDict({
            name: nn.Embedding(size, config.d_model)
            for name, size in config.conditioning_sizes.items()
        })

        layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            layer,
            num_layers=config.num_layers,
            enable_nested_tensor=False,
        )
        self.final_norm = nn.LayerNorm(config.d_model)

        self.output_projection = nn.Linear(
            config.d_model,
            config.vocabulary_size,
            bias=False,
        )
        if config.tie_token_embeddings:
            self.output_projection.weight = self.token_embedding.weight

    def forward(
        self,
        input_ids: Tensor,
        style_id: Tensor,
        substyle_id: Tensor,
        mood_id: Tensor,
        rhythm_id: Tensor,
        role_id: Tensor,
        padding_mask: Tensor | None = None,
    ) -> Tensor:
        if input_ids.ndim != 2:
            raise ValueError("input_ids must have shape [batch, sequence]")
        batch_size, sequence_length = input_ids.shape
        if sequence_length > self.config.max_sequence_length:
            raise ValueError("sequence length exceeds model context")

        positions = torch.arange(
            sequence_length,
            device=input_ids.device,
            dtype=torch.long,
        ).unsqueeze(0)
        hidden = (
            self.token_embedding(input_ids)
            + self.position_embedding(positions)
        )

        for name, ids in (
            ("style", style_id),
            ("substyle", substyle_id),
            ("mood", mood_id),
            ("rhythm", rhythm_id),
            ("role", role_id),
        ):
            if ids.shape != (batch_size,):
                raise ValueError(f"{name}_id must have shape [batch]")
            hidden = hidden + self.condition_embeddings[name](ids).unsqueeze(1)

        causal_mask = torch.triu(
            torch.ones(
                (sequence_length, sequence_length),
                dtype=torch.bool,
                device=input_ids.device,
            ),
            diagonal=1,
        )
        hidden = self.encoder(
            hidden,
            mask=causal_mask,
            src_key_padding_mask=padding_mask,
            is_causal=True,
        )
        return self.output_projection(self.final_norm(hidden))
