"""Exact least-privilege contract for the future hosted CI workflow."""

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT = Path(__file__).parents[1]
WORKFLOW = PROJECT / ".github" / "workflows" / "ci.yml"
EXPECTED_WORKFLOW = """name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.sha }}
          fetch-depth: 1
          submodules: false
          lfs: false
          persist-credentials: false
      - name: Verify event commit
        run: test "$GITHUB_SHA" = "$(git rev-parse HEAD)"
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: ${{ matrix.python-version }}
      - name: Verify complete checkout
        run: |
          PYTHONPYCACHEPREFIX="$RUNNER_TEMP/pycache-${{ matrix.python-version }}" python scripts/verify_distribution.py .
          PYTHONPYCACHEPREFIX="$RUNNER_TEMP/pycache-${{ matrix.python-version }}" python scripts/verify_provenance.py .
      - name: Create reduced source archive
        run: |
          git archive --format=tar \\
            --prefix=decision_evidence_ledger-0.1.0/ \\
            "$GITHUB_SHA" -- . \\
            ':(top,exclude).github/workflows/ci.yml' \\
            ':(top,exclude).gitignore' \\
            ':(top,exclude)docs/LOCAL_RELEASE_GUIDE.md' \\
            ':(top,exclude)tests/test_ci_workflow.py' \\
            > "$RUNNER_TEMP/decision-evidence-ledger-source.tar"
      - name: Verify reduced source archive
        run: |
          PYTHONPYCACHEPREFIX="$RUNNER_TEMP/pycache-${{ matrix.python-version }}" python scripts/verify_distribution.py "$RUNNER_TEMP/decision-evidence-ledger-source.tar"
          PYTHONPYCACHEPREFIX="$RUNNER_TEMP/pycache-${{ matrix.python-version }}" python scripts/verify_provenance.py . --archive "$RUNNER_TEMP/decision-evidence-ledger-source.tar"
      - name: Test and compile
        run: |
          PYTHONPYCACHEPREFIX="$RUNNER_TEMP/pycache-${{ matrix.python-version }}" PYTHONPATH=src python -m unittest discover -s tests -v
          PYTHONPYCACHEPREFIX="$RUNNER_TEMP/pycache-${{ matrix.python-version }}" python -m compileall -q src tests scripts
"""


class CIWorkflowContractTests(unittest.TestCase):
    """Require deliberate review for every workflow privilege or data-flow change."""

    def test_workflow_exists(self) -> None:
        """Catches a missing CI candidate before a hosted push can be considered."""
        self.assertTrue(WORKFLOW.is_file(), "workflow file is required")

    @unittest.skipUnless(WORKFLOW.is_file(), "workflow file is required")
    def test_workflow_is_the_reviewed_literal(self) -> None:
        """Catches unreviewed trigger, privilege, action, command, or runner changes."""
        self.assertEqual(WORKFLOW.read_text(encoding="utf-8"), EXPECTED_WORKFLOW)

    def test_maintainer_documents_route_python_cache_outside_candidate(self) -> None:
        """Catches release documentation that makes a candidate tree impure."""
        cache_prefix = 'PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/decision-evidence-ledger-pycache"'
        for path in (
            PROJECT / "CONTRIBUTING.md",
            PROJECT / "docs" / "LOCAL_RELEASE_GUIDE.md",
        ):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(cache_prefix, text)
                self.assertNotIn("python3 -m venv .venv", text)

    def test_public_compile_commands_cover_every_checked_python_tree(self) -> None:
        """Catches documentation that omits scripts from its local syntax check."""
        for path in (
            PROJECT / "CONTRIBUTING.md",
            PROJECT / "RELEASE_CHECKLIST.md",
            PROJECT / "docs" / "LOCAL_RELEASE_GUIDE.md",
        ):
            with self.subTest(path=path.name):
                self.assertIn(
                    "python3 -m compileall -q src tests scripts",
                    path.read_text(encoding="utf-8"),
                )

    def test_maintainer_install_guide_uses_a_disposable_copy(self) -> None:
        """Catches a release-install rehearsal that can pollute the candidate."""
        guide = (PROJECT / "docs" / "LOCAL_RELEASE_GUIDE.md").read_text(encoding="utf-8")
        self.assertIn("disposable copy", guide)
        self.assertIn("mktemp -d", guide)


if __name__ == "__main__":
    unittest.main()
