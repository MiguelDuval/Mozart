#!/usr/bin/env python3
"""Local REMI/BPE tokenizer recovery scanner tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from recover_remi_bpe_tokenizer import scan_roots  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "remi_tokenizer_fixture.json"


class RemiBpeTokenizerRecoveryTests(unittest.TestCase):
    def test_finds_complete_bpe_tokenizer_and_reports_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "miditok2_12k"
            target.mkdir()
            payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
            (target / "tokenizer.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            (target / "config.json").write_text(
                json.dumps({"vocab_size": 23}), encoding="utf-8"
            )

            report = scan_roots([root], expected_vocab_size=23)

            self.assertEqual(report["tokenizer_files_discovered"], 1)
            self.assertEqual(report["matching_vocabulary_candidates"], 1)
            candidate = report["candidates"][0]
            self.assertEqual(candidate["vocab_size"], 23)
            self.assertEqual(candidate["neighbor_model_vocab_size"], 23)
            self.assertEqual(len(candidate["sha256"]), 64)
            self.assertEqual(candidate["priority"], "high-recovery-lead")
            self.assertIn("does not prove exact checkpoint pairing", report["interpretation"])

    def test_rejects_base_vocabulary_without_learned_bpe_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "tokenizer.json"
            payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
            payload.pop("_model", None)
            target.write_text(json.dumps(payload), encoding="utf-8")

            report = scan_roots([root], expected_vocab_size=23)

            self.assertEqual(report["matching_vocabulary_candidates"], 0)
            self.assertEqual(report["valid_bpe_tokenizers"], 0)
            self.assertEqual(report["rejected_count"], 1)
            self.assertIn("missing the serialized _model", report["rejected_examples"][0]["reason"])

    def test_missing_roots_are_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "not-created"
            report = scan_roots([missing], expected_vocab_size=12000)
            self.assertEqual(report["roots_missing_or_not_directories"], [str(missing)])
            self.assertEqual(report["matching_vocabulary_candidates"], 0)


if __name__ == "__main__":
    unittest.main()
