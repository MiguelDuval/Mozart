import json
from pathlib import Path


def test_model_config_targets_compact_baseline():
    path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "model-training-config.json"
    )
    config = json.loads(path.read_text(encoding="utf-8"))

    assert config["model_id"] == "mozart-symbolic-transformer-v0"
    assert config["vocabulary_id"] == "mozart-midi-events-v1"
    assert config["vocabulary_size"] == 512
    assert config["d_model"] == 576
    assert config["nhead"] == 8
    assert config["num_layers"] == 8
    assert config["dim_feedforward"] == 2304
    assert config["max_sequence_length"] == 1024
    assert config["conditioning"] == {
        "style": 6,
        "substyle": 7,
        "mood": 8,
        "rhythm": 7,
        "role": 8,
    }

    d_model = config["d_model"]
    layers = config["num_layers"]
    ff = config["dim_feedforward"]
    vocab = config["vocabulary_size"]
    context = config["max_sequence_length"]

    per_layer = (
        4 * d_model * d_model
        + 4 * d_model
        + 2 * d_model * ff
        + ff
        + d_model
        + 4 * d_model
    )
    condition_params = sum(
        size * d_model for size in config["conditioning"].values()
    )
    total = (
        vocab * d_model
        + context * d_model
        + condition_params
        + layers * per_layer
        + 2 * d_model
    )

    assert total == config["parameter_count_target"]
    assert 30_000_000 <= total <= 60_000_000
