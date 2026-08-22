"""Package-boundary contract tests."""

from pathlib import Path
import tomllib
import unittest

import decision_evidence_ledger


class PackageBoundaryTests(unittest.TestCase):
    """Ensure published package metadata matches the import contract."""

    def test_imported_version_and_project_metadata_match_public_contract(self):
        """Fails if a release exposes a mismatched package identity or dependency policy."""
        project_root = Path(__file__).resolve().parents[1]
        with (project_root / "pyproject.toml").open("rb") as metadata_file:
            project = tomllib.load(metadata_file)["project"]

        self.assertEqual(decision_evidence_ledger.__version__, "0.1.0")
        self.assertEqual(project["name"], "decision-evidence-ledger")
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["license"], "Apache-2.0")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], [])
        self.assertEqual(project["authors"], [{"name": "liver-detox"}])

    def test_build_metadata_requires_pep_639_capable_setuptools(self):
        """Fails if clean builds may select a backend too old for SPDX metadata."""
        project_root = Path(__file__).resolve().parents[1]
        with (project_root / "pyproject.toml").open("rb") as metadata_file:
            metadata = tomllib.load(metadata_file)

        self.assertEqual(metadata["build-system"]["requires"], ["setuptools>=77"])
        self.assertEqual(metadata["project"]["license-files"], ["LICENSE"])
