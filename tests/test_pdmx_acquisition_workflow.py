#!/usr/bin/env python3
"""Regression tests for the real PDMX acquisition GitHub Actions workflow."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pdmx-acquisition-audit.yml"


class PdmxAcquisitionWorkflowTests(unittest.TestCase):
    def test_workflow_exists_and_uses_current_artifact_actions(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("uses: actions/checkout@v7", content)
        self.assertIn("uses: actions/upload-artifact@v7", content)
        self.assertNotIn("uses: actions/checkout@v6", content)
        self.assertNotIn("\${{ github.sha }}", content)

    def test_multi_file_audit_artifact_uses_normal_archive(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        artifact_marker = "name: pdmx-v9-audit-" + "${{ github.sha }}"
        self.assertIn(artifact_marker, content)
        artifact_block = content.split(artifact_marker, 1)[1]
        self.assertIn("pdmx-audit-v9.json", artifact_block)
        self.assertIn("pdmx-artifact-sha256.txt", artifact_block)
        self.assertIn("pdmx/subset-member.txt", artifact_block)
        self.assertNotIn("archive: false", artifact_block)

    def test_workflow_pins_the_three_official_v9_artifacts(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        expected_urls = (
            "https://zenodo.org/records/15571083/files/mid.tar.gz?download=1",
            "https://zenodo.org/records/15571083/files/PDMX.csv?download=1",
            "https://zenodo.org/records/15571083/files/subset_paths.tar.gz?download=1",
        )
        expected_md5s = (
            "d920a21b2fcd99a56d9c381b39debbb2",
            "30392ccf38bb63ce70e7afae70f9c88c",
            "092eee416ece8060f77d08575b94a43d",
        )
        for url in expected_urls:
            self.assertIn(url, content)
        for digest in expected_md5s:
            self.assertIn(digest, content)

    def test_workflow_extracts_named_subset_and_audits_full_midi_source(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            'tar -tzf subset_paths.tar.gz > "$RUNNER_TEMP/pdmx/subset-paths.list"',
            content,
        )
        self.assertIn("no_license_conflict\\.txt", content)
        self.assertIn(
            '--midi-source "$RUNNER_TEMP/pdmx/mid.tar.gz"',
            content,
        )
        self.assertIn(
            '--output "$RUNNER_TEMP/pdmx/pdmx-audit-v9.json"',
            content,
        )


if __name__ == "__main__":
    unittest.main()
