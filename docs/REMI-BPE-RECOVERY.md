# Recovering the original REMI/BPE tokenizer locally

The immediate goal is to recover the tokenizer used by the existing MusicMaker-derived checkpoint. Do not train another model or replace the current checkpoint as part of this recovery step.

The upstream MusicMaker training source loads a locally saved directory named miditok2_12k, and the tokenizer-training script saves that directory after creating and publishing a private Hub repository. That makes a cached/private copy or the original local training artifact the first place to search. The public shikhr/music_maker/tokenizer.json inspected at the pinned revision is incomplete for the checkpoint: it lacks the serialized learned BPE model and must be rejected.

## Local scan

From the Mozart repository's Python environment, run:

    python tools/recover_remi_bpe_tokenizer.py --report "%USERPROFILE%/Desktop/remi-tokenizer-scan.json"

The scanner checks known Hugging Face cache locations and the repository workspace, and validates each tokenizer.json using the same strict learned-BPE validator as the ONNX exporter. It reports complete tokenizer files with their local path, SHA-256, vocabulary size, special-token IDs, neighbouring config vocabulary size when available, and a Hugging Face cache revision hint. It makes no network requests and uploads no files.

To include other training/output locations, add one or more roots:

    python tools/recover_remi_bpe_tokenizer.py --root "C:/path/to/Cline/workspaces" --root "D:/model-runs" --report "D:/remi-tokenizer-scan.json"

On Windows, use an explicit path for the report if shell-specific quoting or environment-variable expansion differs. The report can contain private local paths; keep it local and do not commit it.

## How to interpret the report

- Prioritize a complete local directory or cache entry associated with shikhr/miditok2_12k.
- A candidate must contain a learned BPE model, unique contiguous IDs beginning at zero, and required special tokens. A base event vocabulary alone does not pass.
- A vocabulary-size match is necessary, but it is not proof that token IDs match the existing checkpoint. Confirm the tokenizer used by the recorded fine-tuning run, or match a recorded tokenizer SHA/revision. Do not pair the weights with a newly trained tokenizer.
- If multiple valid candidates are found, retain their checksums and compare revisions/provenance before choosing. Do not overwrite candidates while investigating.
- Only after the exact tokenizer has been identified should the existing exporter be run on a private copy of the model and tokenizer, outside Git and outside the APK.

## Scope

This scanner discovers and validates local recovery leads. It does not claim the model/tokenizer pairing is verified, does not modify checkpoints, and does not contact Hugging Face. A real export and ONNX/eager parity check remain the next technical verification after recovering the correct artifact.
