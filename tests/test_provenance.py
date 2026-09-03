"""Fail-closed provenance contracts for the local public candidate."""

from __future__ import annotations

import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

from scripts import verify_provenance as verifier
from scripts import verify_distribution as distribution_guard


PROJECT = Path(__file__).parents[1]
VERIFIER = PROJECT / "scripts" / "verify_provenance.py"
SCHEMA_VERSION = "decision-evidence-ledger/public-provenance/v1"
DECISION = "INCLUDE_IN_LOCAL_PUBLIC_CANDIDATE"
SOURCE_ONLY_PATHS = [
    ".github/workflows/ci.yml",
    ".gitignore",
    "docs/LOCAL_RELEASE_GUIDE.md",
    "tests/test_ci_workflow.py",
]

LICENSE_PATH = "LICENSE"
RUNTIME_PATHS = {
    "src/decision_evidence_ledger/__init__.py",
    "src/decision_evidence_ledger/canonical.py",
    "src/decision_evidence_ledger/cli.py",
    "src/decision_evidence_ledger/envelopes.py",
    "src/decision_evidence_ledger/events.py",
    "src/decision_evidence_ledger/ledger.py",
}
SYNTHETIC_PATHS = {
    "examples/SYNTHETIC_assert_payload.json",
    "examples/SYNTHETIC_chain.jsonl",
    "examples/SYNTHETIC_correct_payload.json",
    "examples/SYNTHETIC_metadata.json",
    "examples/SYNTHETIC_withdraw_payload.json",
}
ALL_PATHS = (
    ".github/workflows/ci.yml",
    ".gitignore",
    "CHANGELOG.md",
    "CITATION.cff",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "MANIFEST.in",
    "PROVENANCE.json",
    "README.md",
    "RELEASE_CHECKLIST.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/LOCAL_RELEASE_GUIDE.md",
    "examples/README.md",
    "examples/SYNTHETIC_assert_payload.json",
    "examples/SYNTHETIC_chain.jsonl",
    "examples/SYNTHETIC_correct_payload.json",
    "examples/SYNTHETIC_metadata.json",
    "examples/SYNTHETIC_withdraw_payload.json",
    "examples/rebuild_synthetic_chain.py",
    "pyproject.toml",
    "scripts/__init__.py",
    "scripts/verify_distribution.py",
    "scripts/verify_provenance.py",
    "src/decision_evidence_ledger/__init__.py",
    "src/decision_evidence_ledger/canonical.py",
    "src/decision_evidence_ledger/cli.py",
    "src/decision_evidence_ledger/envelopes.py",
    "src/decision_evidence_ledger/events.py",
    "src/decision_evidence_ledger/ledger.py",
    "tests/__init__.py",
    "tests/test_canonical.py",
    "tests/test_ci_workflow.py",
    "tests/test_cli.py",
    "tests/test_distribution_guard.py",
    "tests/test_envelopes.py",
    "tests/test_events.py",
    "tests/test_ledger.py",
    "tests/test_no_io.py",
    "tests/test_package.py",
    "tests/test_provenance.py",
    "tests/test_rebuild_example.py",
)


def origin_for(path: str) -> str:
    if path == LICENSE_PATH:
        return "STANDARD_APACHE_2_0_LICENSE_TEXT"
    if path in RUNTIME_PATHS:
        return "MAINTAINER_CONTROLLED_CLEAN_REWRITE"
    if path in SYNTHETIC_PATHS:
        return "SYNTHETIC_FIXTURE_CREATED_LOCALLY"
    return "LOCAL_AI_ASSISTED_PROJECT_AUTHORING"


def valid_document() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_status": "V0_1_0_GITHUB_SOURCE_RELEASE_AUTHORIZED",
        "publication_authorization": "GRANTED_FOR_GITHUB_V0_1_0_TAG_AND_HOSTED_SOURCE_RELEASE_ONLY",
        "controller": {
            "public_alias": "liver-detox",
            "development": "LOCAL_AI_ASSISTED",
            "reported_employer_client_coauthor_contract_claim": False,
            "reported_external_source_code_copy_or_adaptation": False,
        },
        "source_only_paths": SOURCE_ONLY_PATHS,
        "files": [
            {"path": path, "origin": origin_for(path), "decision": DECISION}
            for path in ALL_PATHS
        ],
    }


def write_candidate(root: Path, document: dict[str, object] | None = None) -> None:
    for name in ALL_PATHS:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("SYNTHETIC\n", encoding="utf-8")
    (root / "PROVENANCE.json").write_text(
        json.dumps(document or valid_document(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class ProvenanceTests(unittest.TestCase):
    """Exercise the verifier against self-contained synthetic candidates."""

    def test_accepts_the_complete_valid_task_two_contract(self) -> None:
        """Catches removal or rejection of the valid complete provenance contract."""
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            write_candidate(candidate)
            completed = subprocess.run(
                [sys.executable, str(VERIFIER), str(candidate)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "archive_count": None,
                "codes": [],
                "documented_count": 43,
                "observed_count": 43,
                "ok": True,
            },
        )
        self.assertEqual(completed.stderr, "")

    def result_for(self, mutate) -> verifier.ProvenanceResult:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document()
            mutate(root, document)
            write_candidate(root, document)
            return verifier.verify_tree(root)

    def assert_failure_code(self, result: verifier.ProvenanceResult, code: str) -> None:
        self.assertFalse(result.ok)
        self.assertIn(code, result.codes)
        self.assertNotIn("SYNTHETIC_SECRET", " ".join(result.codes))

    def test_rejects_a_documented_file_missing_from_the_tree(self) -> None:
        """Catches a verifier that accepts an incomplete candidate tree."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(root)
            (root / "README.md").unlink()
            result = verifier.verify_tree(root)
        self.assert_failure_code(result, "TREE_MISSING_FILE")

    def test_rejects_extra_files_in_documentation_and_cache_looking_paths(self) -> None:
        """Catches a verifier that ignores extra nested project files."""
        for name in ("docs/build/private.md", ".github/__pycache__/private.py"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_candidate(root)
                extra = root / name
                extra.parent.mkdir(parents=True)
                extra.write_text("SYNTHETIC_SECRET", encoding="utf-8")
                self.assert_failure_code(verifier.verify_tree(root), "TREE_EXTRA_FILE")

    def test_rejects_duplicate_and_unsafe_documented_paths(self) -> None:
        """Catches ambiguous or traversal-shaped provenance path records."""
        cases = (("duplicate", "README.md", "DOCUMENT_DUPLICATE_PATH"), ("unsafe", "../SYNTHETIC_SECRET", "DOCUMENT_UNSAFE_PATH"))
        for kind, path, code in cases:
            with self.subTest(kind=kind):
                def mutate(root: Path, document: dict[str, object], path: str = path) -> None:
                    del root
                    files = document["files"]
                    assert isinstance(files, list)
                    if kind == "duplicate":
                        files.append({"path": path, "origin": origin_for(path), "decision": DECISION})
                    else:
                        files[0]["path"] = path

                self.assert_failure_code(self.result_for(mutate), code)

    def test_rejects_a_non_nfc_documented_path(self) -> None:
        """Catches provenance paths whose Unicode form is not NFC-normalized."""
        def mutate(root: Path, document: dict[str, object]) -> None:
            del root
            files = document["files"]
            assert isinstance(files, list)
            files[0]["path"] = "docs/Cafe\u0301.md"

        self.assert_failure_code(self.result_for(mutate), "DOCUMENT_UNSAFE_PATH")

    def test_rejects_an_unapproved_origin(self) -> None:
        """Catches acceptance of an origin outside the enumerated provenance classes."""
        def mutate(root: Path, document: dict[str, object]) -> None:
            del root
            files = document["files"]
            assert isinstance(files, list)
            files[0]["origin"] = "SYNTHETIC_SECRET"

        self.assert_failure_code(self.result_for(mutate), "DOCUMENT_ORIGIN_INVALID")

    def test_rejects_a_valid_origin_attached_to_the_wrong_path(self) -> None:
        """Catches reclassification of a required runtime path."""
        def mutate(root: Path, document: dict[str, object]) -> None:
            del root
            files = document["files"]
            assert isinstance(files, list)
            for entry in files:
                if entry["path"] == "LICENSE":
                    entry["origin"] = "LOCAL_AI_ASSISTED_PROJECT_AUTHORING"

        self.assert_failure_code(self.result_for(mutate), "DOCUMENT_MAPPING_INVALID")

    def test_rejects_missing_or_nonapproved_inclusion_decisions(self) -> None:
        """Catches entries that are not explicitly approved for the local candidate."""
        for decision in (False, None):
            with self.subTest(decision=decision):
                def mutate(root: Path, document: dict[str, object], decision: object = decision) -> None:
                    del root
                    files = document["files"]
                    assert isinstance(files, list)
                    files[0]["decision"] = decision

                self.assert_failure_code(self.result_for(mutate), "DOCUMENT_DECISION_INVALID")

    def test_rejects_invalid_controller_status_and_publication_fields(self) -> None:
        """Catches a document that changes maintainer-supplied control facts."""
        for field, value in (("candidate_status", "PUBLISHED"), ("publication_authorization", "GRANTED")):
            with self.subTest(field=field):
                def mutate(root: Path, document: dict[str, object], field: str = field, value: str = value) -> None:
                    del root
                    document[field] = value

                self.assert_failure_code(self.result_for(mutate), "DOCUMENT_CONTROLLER_INVALID")

        def mutate_controller(root: Path, document: dict[str, object]) -> None:
            del root
            controller = document["controller"]
            assert isinstance(controller, dict)
            controller["public_alias"] = "SYNTHETIC_SECRET"

        self.assert_failure_code(self.result_for(mutate_controller), "DOCUMENT_CONTROLLER_INVALID")

    def test_rejects_numeric_controller_assertions(self) -> None:
        """Catches Python equality accepting JSON numeric zero as false."""
        fields = (
            "reported_employer_client_coauthor_contract_claim",
            "reported_external_source_code_copy_or_adaptation",
        )
        for field in fields:
            for value in (0, 1):
                with self.subTest(field=field, value=value):
                    def mutate(
                        root: Path,
                        document: dict[str, object],
                        field: str = field,
                        value: int = value,
                    ) -> None:
                        del root
                        controller = document["controller"]
                        assert isinstance(controller, dict)
                        controller[field] = value

                    self.assert_failure_code(
                        self.result_for(mutate), "DOCUMENT_CONTROLLER_INVALID"
                    )

    def test_rejects_malformed_and_duplicate_key_json(self) -> None:
        """Catches parser ambiguity before the ledger can be trusted."""
        for payload, code in (("{", "DOCUMENT_JSON_INVALID"), ('{"schema_version":"a","schema_version":"b"}', "DOCUMENT_JSON_DUPLICATE_KEY")):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_candidate(root)
                (root / "PROVENANCE.json").write_text(payload, encoding="utf-8")
                self.assert_failure_code(verifier.verify_tree(root), code)

    def test_cli_maps_deep_json_recursion_to_one_safe_verdict(self) -> None:
        """Catches a valid-sized but deeply nested ledger escaping the CLI."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(root)
            (root / "PROVENANCE.json").write_text(
                '{"x":' * 10_000 + "0" + "}" * 10_000,
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        f"sys.path.insert(0, {str(PROJECT)!r}); "
                        "from scripts import verify_provenance as verifier; "
                        "original = verifier.json.loads; "
                        "exec('def loads(*args, **kwargs):\\n"
                        "    original(*args, **kwargs)\\n"
                        "    raise RecursionError'); "
                        "verifier.json.loads = loads; "
                        "sys.setrecursionlimit(100); "
                        "raise SystemExit(verifier.main([sys.argv[1]]))"
                    ),
                    str(root),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(len(completed.stdout.splitlines()), 1)
        self.assertEqual(
            json.loads(completed.stdout)["codes"], ["DOCUMENT_JSON_INVALID"]
        )
        self.assertNotIn(str(root), completed.stdout + completed.stderr)

    def test_rejects_root_git_file_or_symlink_and_nested_git_directory(self) -> None:
        """Catches non-control Git-shaped objects and hidden nested repositories."""
        cases = (("file", ".git"), ("symlink", ".git"), ("nested", "docs/.git"))
        for kind, name in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_candidate(root)
                target = root / name
                if kind == "file":
                    target.write_text("SYNTHETIC_SECRET", encoding="utf-8")
                    code = "ROOT_GIT_INVALID"
                elif kind == "symlink":
                    target.symlink_to(root / "README.md")
                    code = "ROOT_GIT_INVALID"
                else:
                    target.mkdir()
                    code = "NESTED_GIT_INVALID"
                self.assert_failure_code(verifier.verify_tree(root), code)

    def test_rejects_any_non_git_symlink(self) -> None:
        """Catches traversal through or publication of symlinked material."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(root)
            (root / "docs" / "linked.md").symlink_to(root / "README.md")
            self.assert_failure_code(verifier.verify_tree(root), "TREE_SYMLINK_INVALID")

    def test_does_not_read_an_external_valid_ledger_through_a_symlink(self) -> None:
        """Catches a ledger read that follows a candidate-file symlink."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "candidate")
            external_ledger = Path(directory, "external-ledger.json")
            root.mkdir()
            write_candidate(root)
            external_ledger.write_text(
                json.dumps(valid_document(), sort_keys=True), encoding="utf-8"
            )
            (root / "PROVENANCE.json").unlink()
            (root / "PROVENANCE.json").symlink_to(external_ledger)
            result = verifier.verify_tree(root)

        self.assert_failure_code(result, "DOCUMENT_READ_UNSAFE")
        self.assertEqual(result.documented_count, 0)

    def test_does_not_read_a_candidate_through_a_root_symlink(self) -> None:
        """Catches a root path that is resolved after the symlink safety check."""
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory, "candidate")
            linked_root = Path(directory, "linked-candidate")
            candidate.mkdir()
            write_candidate(candidate)
            linked_root.symlink_to(candidate, target_is_directory=True)
            result = verifier.verify_tree(linked_root)

        self.assert_failure_code(result, "ROOT_SYMLINK_INVALID")
        self.assertEqual(result.documented_count, 0)
        self.assertEqual(result.observed_count, 0)

    def test_rejects_a_fifo_ledger_without_blocking_or_reading_it(self) -> None:
        """Catches opening a special ledger file before its type is validated."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(root)
            ledger = root / "PROVENANCE.json"
            ledger.unlink()
            os.mkfifo(ledger)
            try:
                completed = subprocess.run(
                    [sys.executable, str(VERIFIER), str(root)],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=1,
                )
            except subprocess.TimeoutExpired:
                self.fail("special ledger read blocked")

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertIn("DOCUMENT_READ_UNSAFE", payload["codes"])
        self.assertEqual(payload["documented_count"], 0)
        self.assertNotIn("SYNTHETIC_SECRET", completed.stdout + completed.stderr)

    def test_ignores_only_a_real_root_git_directory(self) -> None:
        """Catches accidental rejection of ordinary root version-control metadata."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_candidate(root)
            (root / ".git").mkdir()
            result = verifier.verify_tree(root)
        self.assertTrue(result.ok, result.codes)

    def test_cli_read_failure_is_a_safe_json_verdict(self) -> None:
        """Catches CLI read errors that reveal an argument or raise a traceback."""
        completed = subprocess.run(
            [sys.executable, str(VERIFIER), "SYNTHETIC_SECRET"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(json.loads(completed.stdout)["codes"], ["DOCUMENT_JSON_INVALID", "TREE_READ_ERROR"])
        self.assertNotIn("SYNTHETIC_SECRET", completed.stdout + completed.stderr)

    def test_rejects_unsorted_duplicate_undocumented_missing_and_reclassified_source_only_policy(self) -> None:
        """Catches every way callers could loosen the fixed Task-2 source-only policy."""
        cases = (
            ("unsorted", [".gitignore", ".github/workflows/ci.yml", "docs/LOCAL_RELEASE_GUIDE.md", "tests/test_ci_workflow.py"], "SOURCE_ONLY_UNSORTED"),
            ("duplicate", [".github/workflows/ci.yml", ".github/workflows/ci.yml"], "SOURCE_ONLY_DUPLICATE"),
            ("undocumented", [".github/workflows/ci.yml", ".gitignore", "docs/LOCAL_RELEASE_GUIDE.md", "missing.md"], "SOURCE_ONLY_UNDOCUMENTED"),
            ("missing", [".github/workflows/ci.yml", ".gitignore", "docs/LOCAL_RELEASE_GUIDE.md"], "SOURCE_ONLY_POLICY_MISSING"),
            ("reclassified", [".github/workflows/ci.yml", ".gitignore", "README.md", "tests/test_ci_workflow.py"], "SOURCE_ONLY_RECLASSIFIED"),
        )
        for kind, paths, code in cases:
            with self.subTest(kind=kind):
                def mutate(root: Path, document: dict[str, object], paths: list[str] = paths) -> None:
                    del root
                    document["source_only_paths"] = paths

                self.assert_failure_code(self.result_for(mutate), code)

    def test_cli_fails_closed_without_echoing_bad_arguments_or_paths(self) -> None:
        """Catches a CLI that crashes or reports caller-controlled argument text."""
        completed = subprocess.run(
            [sys.executable, str(VERIFIER), "--unknown=SYNTHETIC_SECRET"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(json.loads(completed.stdout)["codes"], ["CLI_ARGUMENT_ERROR"])
        self.assertNotIn("SYNTHETIC_SECRET", completed.stdout + completed.stderr)


class ArchiveProvenanceTests(unittest.TestCase):
    """Require an exact, Git-shaped source archive rather than a partial export."""

    prefix = "decision_evidence_ledger-0.1.0"

    def _write_member(self, archive: tarfile.TarFile, name: str, payload: bytes = b"SYNTHETIC\n") -> None:
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    def _write_directory(self, archive: tarfile.TarFile, name: str) -> None:
        member = tarfile.TarInfo(name)
        member.type = tarfile.DIRTYPE
        archive.addfile(member)

    def make_archive(self, path: Path, *, mutate=None) -> None:
        expected = tuple(path for path in ALL_PATHS if path not in SOURCE_ONLY_PATHS)
        ancestors = sorted(
            {
                "/".join(parts[:index])
                for name in expected
                for parts in [name.split("/")]
                for index in range(1, len(parts))
            }
        )
        with tarfile.open(path, "w") as archive:
            self._write_directory(archive, self.prefix + "/")
            for ancestor in ancestors:
                self._write_directory(archive, f"{self.prefix}/{ancestor}/")
            for name in expected:
                self._write_member(archive, f"{self.prefix}/{name}")
            if mutate is not None:
                mutate(archive, expected)

    def result_for(self, mutate=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "candidate")
            root.mkdir()
            write_candidate(root)
            archive_path = Path(directory, "candidate.tar")
            self.make_archive(archive_path, mutate=mutate)
            return verifier.verify_tree(root, archive_path=archive_path)

    def test_accepts_exact_git_shaped_archive_and_does_not_count_directories(self) -> None:
        """Catches archive validation missing a required ordinary project member."""
        result = self.result_for()
        self.assertTrue(result.ok, result.codes)
        self.assertEqual(result.archive_count, 39)
        self.assertEqual(result.documented_count, 43)
        self.assertEqual(result.observed_count, 43)

    def test_cli_accepts_archive_and_reports_only_ordinary_member_count(self) -> None:
        """Catches a CLI that silently omits its reviewed archive verification branch."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "candidate")
            root.mkdir()
            write_candidate(root)
            archive_path = Path(directory, "candidate.tar")
            self.make_archive(archive_path)
            completed = subprocess.run(
                [sys.executable, str(VERIFIER), str(root), "--archive", str(archive_path)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["archive_count"], 39)
        self.assertEqual(completed.stderr, "")

    def test_rejects_missing_and_extra_archive_files(self) -> None:
        """Catches incomplete or expanded archives despite a valid source checkout."""
        # A separate archive without the last expected member is built directly.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "candidate")
            root.mkdir()
            write_candidate(root)
            archive_path = Path(directory, "missing.tar")
            expected = tuple(path for path in ALL_PATHS if path not in SOURCE_ONLY_PATHS)
            with tarfile.open(archive_path, "w") as archive:
                self._write_directory(archive, self.prefix + "/")
                for name in expected[:-1]:
                    self._write_member(archive, f"{self.prefix}/{name}")
            missing_result = verifier.verify_tree(root, archive_path=archive_path)

        extra_result = self.result_for(
            lambda archive, expected: self._write_member(
                archive, f"{self.prefix}/SYNTHETIC_SECRET.py"
            )
        )
        self.assertIn("ARCHIVE_MISSING_FILE", missing_result.codes)
        self.assertIn("ARCHIVE_EXTRA_FILE", extra_result.codes)

    def test_rejects_wrong_prefix_duplicate_extra_directory_and_unsafe_member(self) -> None:
        """Catches archive layout ambiguity before content is treated as a source distribution."""
        wrong_prefix = self.result_for(
            lambda archive, expected: self._write_member(archive, "wrong/README.md")
        )
        duplicate = self.result_for(
            lambda archive, expected: self._write_member(archive, f"{self.prefix}/README.md")
        )
        extra_directory = self.result_for(
            lambda archive, expected: self._write_directory(archive, f"{self.prefix}/unused/")
        )
        unsafe = self.result_for(
            lambda archive, expected: self._write_member(archive, f"{self.prefix}/../SYNTHETIC_SECRET.py")
        )
        self.assertIn("ARCHIVE_PREFIX_INVALID", wrong_prefix.codes)
        self.assertIn("ARCHIVE_DUPLICATE_MEMBER", duplicate.codes)
        self.assertIn("ARCHIVE_EXTRA_DIRECTORY", extra_directory.codes)
        self.assertIn("ARCHIVE_UNSAFE_PATH", unsafe.codes)

    def test_rejects_archive_exceeding_shared_member_limit(self) -> None:
        """Catches provenance parsing an archive beyond the shared resource budget."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "candidate")
            root.mkdir()
            write_candidate(root)
            archive_path = Path(directory, "too-many-members.tar")
            with tarfile.open(archive_path, "w") as archive:
                for index in range(distribution_guard.MAX_MEMBERS + 1):
                    self._write_member(
                        archive,
                        f"{self.prefix}/SYNTHETIC-{index}",
                    )
            result = verifier.verify_tree(root, archive_path=archive_path)

        self.assertEqual(result.codes, ("TOO_MANY_MEMBERS",))
        self.assertEqual(result.archive_count, 0)

    def test_rejects_regular_members_that_differ_only_by_a_trailing_slash(self) -> None:
        """Catches a duplicate logical file bypassing raw TAR member-name checks."""
        result = self.result_for(
            lambda archive, expected: self._write_member(
                archive, f"{self.prefix}/README.md/"
            )
        )
        self.assertFalse(result.ok)
        self.assertIn("ARCHIVE_DUPLICATE_MEMBER", result.codes)

    def test_rejects_hardlink_symlink_device_fifo_and_other_special_members(self) -> None:
        """Catches non-regular TAR members, all of which must fail without path output."""
        types = (
            tarfile.LNKTYPE,
            tarfile.SYMTYPE,
            tarfile.CHRTYPE,
            tarfile.FIFOTYPE,
            tarfile.CONTTYPE,
        )
        for member_type in types:
            with self.subTest(member_type=member_type):
                def mutate(archive: tarfile.TarFile, expected: tuple[str, ...], member_type: bytes = member_type) -> None:
                    del expected
                    member = tarfile.TarInfo(f"{self.prefix}/SYNTHETIC_SECRET")
                    member.type = member_type
                    member.linkname = "README.md"
                    archive.addfile(member)

                result = self.result_for(mutate)
                self.assertFalse(result.ok)
                self.assertIn("ARCHIVE_SPECIAL_MEMBER", result.codes)
                self.assertNotIn("SYNTHETIC_SECRET", " ".join(result.codes))


if __name__ == "__main__":
    unittest.main()
