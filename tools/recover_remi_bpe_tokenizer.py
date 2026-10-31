#!/usr/bin/env python3
"""Find complete local MidiTok REMI/BPE tokenizer artifacts without network access.

A matching vocabulary size is only a recovery lead. It does not prove that a
tokenizer's token IDs are paired with a particular checkpoint.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from export_remi_bpe_onnx import inspect_miditok_tokenizer  # noqa: E402

PRUNED_DIRS = {
    ".git", ".hg", ".svn", ".venv", ".venv-aura", "venv", "env",
    "node_modules", "__pycache__", ".gradle", "build", "dist",
    "site-packages", ".idea",
}


def default_roots() -> list[Path]:
    """Return conservative local roots; callers can add training/cache roots."""
    home = Path.home()
    roots: list[Path] = []
    for variable in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value).expanduser())
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        hf_home_path = Path(hf_home).expanduser()
        roots.extend((hf_home_path / "hub", hf_home_path))
    roots.extend((
        home / ".cache" / "huggingface" / "hub",
        home / "AppData" / "Local" / "huggingface" / "hub",
        ROOT,
    ))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in roots:
        key = str(path.resolve(strict=False)).casefold()
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def _tokenizer_files(root: Path):
    """Walk without following symlinked directories or entering build environments."""
    for directory, child_dirs, filenames in os.walk(root, followlinks=False):
        child_dirs[:] = [
            name for name in child_dirs
            if name not in PRUNED_DIRS and not name.startswith(".pytest_cache")
        ]
        if "tokenizer.json" in filenames:
            yield Path(directory) / "tokenizer.json"


def _source_hint(path: Path) -> str:
    normalized = str(path).replace("\\", "/").casefold()
    if "models--shikhr--miditok2_12k" in normalized:
        return "shikhr/miditok2_12k Hub-cache path (high-priority recovery lead; pairing still unverified)"
    if "/miditok2_12k/" in normalized or normalized.endswith("/miditok2_12k/tokenizer.json"):
        return "directory named miditok2_12k (name alone does not prove provenance)"
    if "models--shikhr--music_maker" in normalized:
        return "shikhr/music_maker Hub-cache path (published tokenizer previously found incomplete)"
    return "local tokenizer file (provenance not inferred)"


def _snapshot_revision(path: Path) -> str | None:
    # Hugging Face cache layout: .../snapshots/<commit>/tokenizer.json
    if path.parent.parent.name == "snapshots":
        candidate = path.parent.name
        if len(candidate) == 40 and all(c in "0123456789abcdefABCDEF" for c in candidate):
            return candidate
    return None


def _neighbor_model_vocab(path: Path) -> int | None:
    config_path = path.parent / "config.json"
    if not config_path.is_file():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = config.get("vocab_size") if isinstance(config, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def download_hub_snapshot(repo_id: str, revision: str = "main") -> Path:
    """Download only tokenizer/config metadata, using locally configured Hub auth."""
    parts = repo_id.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Hub repository must use the namespace/repository form")
    if not revision.strip():
        raise ValueError("Hub revision must not be empty")

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "Hugging Face lookup requires huggingface_hub; install huggingface_hub==0.23.4"
        ) from exc

    # token=None lets huggingface_hub use the user's existing local login or
    # HF_TOKEN configuration when available; this tool never reads or prints it.
    snapshot = snapshot_download(
        repo_id=repo_id,
        revision=revision,
        allow_patterns=["tokenizer.json", "config.json"],
    )
    path = Path(snapshot)
    if not path.is_dir():
        raise RuntimeError("Hugging Face snapshot download did not return a directory")
    return path


def scan_roots(roots: list[Path], expected_vocab_size: int = 12000) -> dict[str, Any]:
    """Inspect locally found tokenizer.json files and report valid BPE candidates."""
    if isinstance(expected_vocab_size, bool) or expected_vocab_size < 1:
        raise ValueError("expected vocabulary size must be a positive integer")

    scanned_roots: list[str] = []
    missing_roots: list[str] = []
    discovered: dict[str, Path] = {}
    for raw_root in roots:
        root = raw_root.expanduser()
        if not root.exists() or not root.is_dir():
            missing_roots.append(str(root))
            continue
        resolved_root = root.resolve()
        scanned_roots.append(str(resolved_root))
        for path in _tokenizer_files(resolved_root):
            try:
                path.resolve(strict=True)  # Check that a cache symlink target exists.
            except OSError:
                continue
            # Keep the snapshot path, not the resolved blobs/ path: the snapshot
            # directory encodes the immutable Hub revision used for provenance.
            discovered.setdefault(str(path), path)

    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for path in discovered.values():
        try:
            contract = inspect_miditok_tokenizer(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            rejected.append({"path": str(path), "reason": str(exc)})
            continue

        model_vocab = _neighbor_model_vocab(path)
        candidate = {
            "path": str(path),
            "source_hint": _source_hint(path),
            "snapshot_revision_hint": _snapshot_revision(path),
            "sha256": contract["tokenizer_sha256"],
            "vocab_size": contract["vocab_size"],
            "expected_vocab_size_match": contract["vocab_size"] == expected_vocab_size,
            "neighbor_model_vocab_size": model_vocab,
            "neighbor_model_vocab_match": model_vocab == contract["vocab_size"] if model_vocab is not None else None,
            "special_token_ids": contract["special_token_ids"],
            "tokenizer_config": contract["config"],
        }
        if candidate["expected_vocab_size_match"]:
            if "miditok2_12k" in candidate["source_hint"].casefold() or "models--shikhr--miditok2_12k" in str(path).casefold():
                candidate["priority"] = "high-recovery-lead"
            else:
                candidate["priority"] = "vocabulary-match-only"
        else:
            candidate["priority"] = "valid-bpe-but-vocabulary-size-differs"
        valid.append(candidate)

    valid.sort(key=lambda item: (
        not item["expected_vocab_size_match"],
        item["priority"] != "high-recovery-lead",
        item["path"].casefold(),
    ))
    matches = [item for item in valid if item["expected_vocab_size_match"]]
    return {
        "expected_vocab_size": expected_vocab_size,
        "roots_scanned": scanned_roots,
        "roots_missing_or_not_directories": missing_roots,
        "tokenizer_files_discovered": len(discovered),
        "valid_bpe_tokenizers": len(valid),
        "matching_vocabulary_candidates": len(matches),
        "candidates": valid,
        "rejected_count": len(rejected),
        "rejected_examples": rejected[:50],
        "interpretation": (
            "A complete BPE vocabulary with the expected size is only a candidate. "
            "It does not prove exact checkpoint pairing. Confirm the training-time tokenizer "
            "path/revision or recorded SHA-256 before exporting or claiming compatibility."
        ),
        "network_access": "not used; this scan is local-only",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", action="append", type=Path, default=None,
        help="additional local directory to scan; repeat for Hugging Face caches and training outputs",
    )
    parser.add_argument(
        "--hub-repo", action="append", default=None,
        help="optional Hugging Face repo to check with locally configured auth; fetches only tokenizer.json and config.json",
    )
    parser.add_argument(
        "--hub-revision", default="main",
        help="revision for every --hub-repo lookup (default: main; resolved commit is recorded)",
    )
    parser.add_argument(
        "--expected-vocab-size", type=int, default=12000,
        help="expected external checkpoint vocabulary size (default: 12000)",
    )
    parser.add_argument(
        "--report", type=Path,
        help="optional path for a JSON report; defaults to stdout only",
    )
    args = parser.parse_args(argv)
    roots = default_roots()
    if args.root:
        roots.extend(args.root)

    hub_lookups: list[dict[str, Any]] = []
    for repo_id in args.hub_repo or []:
        try:
            snapshot = download_hub_snapshot(repo_id, args.hub_revision)
            roots.append(snapshot)
            tokenizer_path = snapshot / "tokenizer.json"
            config_path = snapshot / "config.json"
            hub_lookups.append({
                "repo_id": repo_id,
                "requested_revision": args.hub_revision,
                "status": "downloaded",
                "snapshot_path": str(snapshot),
                "snapshot_revision_hint": _snapshot_revision(tokenizer_path),
                "tokenizer_present": tokenizer_path.is_file(),
                "config_present": config_path.is_file(),
                "downloaded_files": ["tokenizer.json", "config.json"],
            })
        except Exception as exc:
            print(
                f"Hub lookup for {repo_id} failed ({type(exc).__name__}). "
                "Check the repository/revision, network, and locally configured Hugging Face access.",
                file=sys.stderr,
            )
            hub_lookups.append({
                "repo_id": repo_id,
                "requested_revision": args.hub_revision,
                "status": "inaccessible_or_missing",
                "error_type": type(exc).__name__,
                "downloaded_files": [],
            })

    report = scan_roots(roots, args.expected_vocab_size)
    if hub_lookups:
        report["hub_lookups"] = hub_lookups
        report["network_access"] = "used only for explicitly requested --hub-repo metadata downloads"
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        report_path = args.report.expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")
        print(f"Local tokenizer scan report written to: {report_path}")
        print(
            f"Discovered {report['tokenizer_files_discovered']} tokenizer files; "
            f"{report['matching_vocabulary_candidates']} valid BPE candidate(s) match "
            f"vocab size {args.expected_vocab_size}."
        )
    else:
        print(rendered, end="")
    return 0 if report["matching_vocabulary_candidates"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
