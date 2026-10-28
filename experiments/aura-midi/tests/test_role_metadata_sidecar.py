#!/usr/bin/env python3
"""Offline tests for metadata sidecar identity, provenance, and conditioning counts."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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
            (root / "train" / "progression_001.mid").write_bytes(b"fixture")
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
            (root / "train" / "groove.mid").write_bytes(b"fixture")
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

    def test_make_record_piano_has_no_weak_role_candidate(self):
        row = MODULE.make_record(
            source_id="maestro", composition_id="c1", asset_id="a1.mid",
            midi_path="a1.mid", asset_exists=True, split="train",
            license_name="CC BY-NC-SA 4.0", source_domain="classical_solo_piano",
            source_role="Piano", role_origin="dataset_semantics",
            role_kind="instrument_identity_not_functional_role", role_confidence=1.0,
            instrument_class="Piano",
        )
        self.assertIsNone(row["weak_role_candidate"])
        self.assertIsNone(row["weak_role_confidence"])
        self.assertIsNone(row["heuristic_rule_version"])
        self.assertEqual(row["source_role_label"], "Piano")
        self.assertEqual(row["source_role_kind"], "instrument_identity_not_functional_role")

    def test_asset_id_collision_does_not_merge_different_compositions(self):
        """Same asset_id under different composition_id must remain separate rows."""
        rows = [
            MODULE.make_record(
                source_id="slakh2100_samples", composition_id="Track00001", asset_id="S00",
                midi_path="/fixture/S00.mid", asset_exists=True, split="train",
                license_name="CC BY-NC 4.0", source_domain="multitrack_midi_stems",
                instrument_class="Electric Bass", is_drum=False,
            ),
            MODULE.make_record(
                source_id="slakh2100_samples", composition_id="Track00002", asset_id="S00",
                midi_path="/fixture/S00.mid", asset_exists=True, split="train",
                license_name="CC BY-NC 4.0", source_domain="multitrack_midi_stems",
                instrument_class="Drums", is_drum=True,
            ),
        ]
        deduped, duplicates = MODULE.deduplicate_asset_rows(rows)
        self.assertEqual(duplicates, 0)
        self.assertEqual(len(deduped), 2)
        self.assertEqual({r["composition_id"] for r in deduped}, {"Track00001", "Track00002"})

    def test_rebuild_is_reproducible_without_source_changes(self):
        """Running dedup on the same inputs yields identical rows."""
        base = [
            MODULE.make_record(
                source_id="nrgcp", composition_id="c1", asset_id="a1.mid",
                midi_path="/f/a1.mid", asset_exists=True, split="train",
                license_name="CC BY 4.0", source_domain="chords",
                source_role="Chords/Harmony", role_origin="dataset_semantics",
                role_kind="musical_function", role_confidence=1.0,
            ),
            MODULE.make_record(
                source_id="gmd", composition_id="g1", asset_id="g1.mid",
                midi_path="/f/g1.mid", asset_exists=True, split="train",
                license_name="CC BY 4.0", source_domain="drums",
                source_role="Drums", role_origin="dataset_semantics",
                role_kind="musical_function", role_confidence=1.0,
                source_style="dance/disco",
            ),
        ]
        deduped1, _ = MODULE.deduplicate_asset_rows(list(base))
        deduped2, _ = MODULE.deduplicate_asset_rows(list(base))
        self.assertEqual(deduped1, deduped2)

    def test_incomplete_record_preserves_missing_values(self):
        """Records with missing optional fields keep None/absent rather than guessing."""
        row = MODULE.make_record(
            source_id="unknown", composition_id="c1", asset_id="a1.mid",
            midi_path=None, asset_exists=False, split="unknown",
            license_name="Unknown", source_domain="unknown",
        )
        self.assertIsNone(row["midi_path"])
        self.assertFalse(row["asset_exists"])
        self.assertIsNone(row["source_role_label"])
        self.assertIsNone(row["weak_role_candidate"])
        self.assertIsNone(row["genre_label"])
        self.assertIsNone(row["section_label"])

    def test_asset_deduplication_keeps_all_stems_and_performances(self):
        def record(source, composition, asset):
            return MODULE.make_record(
                source_id=source, composition_id=composition, asset_id=asset,
                midi_path=f"/fixture/{composition}/{asset}.mid", asset_exists=True,
                split="train", license_name="CC BY 4.0", source_domain="fixture",
            )

        input_rows = [
            record("slakh2100_samples", "Track00001", "S00"),
            record("slakh2100_samples", "Track00001", "S01"),
            record("slakh2100_samples", "Track00002", "S00"),
            record("maestro", "piece-A", "performance-1"),
            record("maestro", "piece-A", "performance-2"),
            record("maestro", "piece-A", "performance-1"),  # exact duplicate only
        ]
        result, duplicates = MODULE.deduplicate_asset_rows(input_rows)
        self.assertEqual(duplicates, 1)
        self.assertEqual(len(result), 5)
        self.assertEqual(
            {(r["composition_id"], r["asset_id"]) for r in result if r["source_id"] == "slakh2100_samples"},
            {("Track00001", "S00"), ("Track00001", "S01"), ("Track00002", "S00")},
        )
        maestro_assets = {r["asset_id"] for r in result if r["source_id"] == "maestro"}
        self.assertEqual(maestro_assets, {"performance-1", "performance-2"})

    def test_slakh_keeps_unsaved_metadata_rows_and_reads_inst_class(self):
        original_yaml = MODULE.yaml
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for comp in ("Track00001", "Track00002"):
                comp_root = root / comp
                comp_root.mkdir()
                (comp_root / "metadata.yaml").write_text(comp, encoding="utf-8")
                (comp_root / "S00.mid").write_bytes(b"fixture")

            class FixtureYaml:
                @staticmethod
                def safe_load(text):
                    return {
                        "stems": {
                            "S00": {"midi_saved": True, "inst_class": "Electric Bass", "is_drum": False},
                            "S06": {"midi_saved": False, "inst_class": "Drums", "is_drum": True},
                        }
                    }

            MODULE.yaml = FixtureYaml
            try:
                rows, info = MODULE.slakh_records(root)
            finally:
                MODULE.yaml = original_yaml

            self.assertEqual(info["stems_seen"], 4)
            self.assertEqual(info["midi_saved_true_stems"], 2)
            self.assertEqual(info["midi_saved_false_stems"], 2)
            self.assertEqual(info["stems_without_midi_path"], 2)
            self.assertEqual(len({r["composition_id"] for r in rows}), 2)
            bass_rows = [r for r in rows if r["asset_id"] == "S00"]
            self.assertEqual(len(bass_rows), 2)
            self.assertTrue(all(r["weak_role_candidate"] == "Bass" for r in bass_rows))
            unsaved = [r for r in rows if r["asset_id"] == "S06"]
            self.assertEqual(len(unsaved), 2)
            self.assertTrue(all(r["midi_saved"] is False and not r["asset_exists"] for r in unsaved))
            self.assertTrue(all(r["weak_role_candidate"] == "Drums" for r in unsaved))

    def test_summary_reports_trustworthy_labels_by_split(self):
        rows = [
            MODULE.make_record(
                source_id="nrgcp", composition_id="n1", asset_id="n1.mid",
                midi_path="n1.mid", asset_exists=True, split="unknown",
                license_name="CC BY 4.0", source_domain="chords",
                source_role="Chords/Harmony", role_origin="dataset_semantics",
                role_kind="musical_function", role_confidence=1.0,
            ),
            MODULE.make_record(
                source_id="gmd", composition_id="g1", asset_id="g1.mid",
                midi_path="g1.mid", asset_exists=True, split="train",
                license_name="CC BY 4.0", source_domain="drums",
                source_role="Drums", role_origin="dataset_semantics",
                role_kind="musical_function", role_confidence=1.0,
                source_style="dance/disco",
            ),
        ]
        summary = MODULE.summarize(rows, {"nrgcp": {"status": "OK"}, "gmd": {"status": "OK"}})
        by_source = {r["source_name"]: r for r in summary["corpora"]}
        self.assertEqual(by_source["nrgcp"]["functional_role_labels_by_split"], {"unknown": {"Chords/Harmony": 1}})
        self.assertEqual(by_source["gmd"]["functional_role_labels_by_split"], {"train": {"Drums": 1}})
        self.assertEqual(by_source["gmd"]["source_style_labels_by_split"], {"train": {"dance/disco": 1}})
        self.assertEqual(by_source["maestro"]["asset_records"], 0)

    def test_maestro_performances_link_to_composition_without_being_collapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "train").mkdir()
            (root / "validation").mkdir()
            (root / "train" / "perf_a.mid").write_bytes(b"a")
            (root / "validation" / "perf_b.mid").write_bytes(b"b")
            csv_path = root / "maestro.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["midi_filename", "split", "title"])
                writer.writeheader()
                writer.writerow({"midi_filename": "train/perf_a.mid", "split": "train", "title": "Same Piece"})
                writer.writerow({"midi_filename": "validation/perf_b.mid", "split": "validation", "title": "Same Piece"})
            rows, _ = MODULE.csv_records(csv_path, "maestro")
            deduped, duplicates = MODULE.deduplicate_asset_rows(rows)
            summary = MODULE.summarize(deduped, {"maestro": {"status": "OK"}})
            maestro = next(r for r in summary["corpora"] if r["source_name"] == "maestro")
            self.assertEqual(len(deduped), 2)
            self.assertEqual(duplicates, 0)
            self.assertEqual(maestro["asset_records"], 2)
            self.assertEqual(maestro["unique_compositions"], 1)
            self.assertEqual(maestro["compositions_present_in_multiple_splits"], 1)
            self.assertEqual(maestro["instrument_identity_labels_by_split"], {
                "train": {"Piano": 1}, "validation": {"Piano": 1}
            })

    def test_script_is_metadata_only(self):
        code = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("import torch", code)
        self.assertNotIn("torch.load", code)
        self.assertNotIn("subprocess", code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
