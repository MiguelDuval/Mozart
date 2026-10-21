#!/usr/bin/env python3
"""Offline unit tests for build_role_metadata_sidecar; no PyTorch or MIDI parser."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "build_role_metadata_sidecar.py"
SPEC = importlib.util.spec_from_file_location("build_role_metadata_sidecar", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RoleMetadataSidecarTests(unittest.TestCase):
    def test_nrgcp_source_role_and_split_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "train").mkdir()
            midi = root / "train" / "progression_001.mid"
            midi.write_bytes(b"fixture")
            rows, info = MODULE.nrgcp_records(root)
            self.assertEqual(info["files_seen"], 1)
            self.assertEqual(rows[0]["source_role_label"], "Chords/Harmony")
            self.assertEqual(rows[0]["role_label_origin"], "dataset_semantics")
            self.assertEqual(rows[0]["split"], "train")
            self.assertIsNone(rows[0]["genre_label"])

    def test_gmd_style_is_not_promoted_to_genre(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "train").mkdir()
            midi = root / "train" / "groove.mid"
            midi.write_bytes(b"fixture")
            csv_path = root / "info.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["midi_filename", "split", "style"])
                writer.writeheader()
                writer.writerow({"midi_filename": "train/groove.mid", "split": "train", "style": "dance/disco"})
            rows, info = MODULE.csv_records(csv_path, "gmd")
            self.assertEqual(info["rows_seen"], 1)
            self.assertTrue(rows[0]["asset_exists"])
            self.assertEqual(rows[0]["source_role_label"], "Drums")
            self.assertEqual(rows[0]["source_style_label"], "dance/disco")
            self.assertIsNone(rows[0]["genre_label"])
            self.assertEqual(rows[0]["split"], "train")

    def test_maestro_piano_identity_is_not_functional_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "validation").mkdir()
            (root / "validation" / "piece.mid").write_bytes(b"fixture")
            csv_path = root / "maestro.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["midi_filename", "split"])
                writer.writeheader()
                writer.writerow({"midi_filename": "validation/piece.mid", "split": "validation"})
            rows, _ = MODULE.csv_records(csv_path, "maestro")
            self.assertEqual(rows[0]["source_role_label"], "Piano")
            self.assertEqual(rows[0]["source_role_kind"], "instrument_identity_not_functional_role")
            self.assertEqual(rows[0]["split"], "validation")
            self.assertEqual(rows[0]["license_use_class"], "noncommercial_only")

    def test_ambiguous_instrument_classes_do_not_get_fake_role(self):
        self.assertEqual(MODULE.weak_role_candidate("Electric Bass"), ("Bass", 0.72))
        self.assertEqual(MODULE.weak_role_candidate("Synth Lead"), ("Melody", 0.65))
        self.assertEqual(MODULE.weak_role_candidate("Piano"), (None, None))
        self.assertEqual(MODULE.weak_role_candidate("Guitar"), (None, None))

    def test_script_is_metadata_only(self):
        code = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("import torch", code)
        self.assertNotIn("torch.load", code)
        self.assertNotIn("subprocess", code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
