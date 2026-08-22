"""Fail-closed contracts for the source and distribution privacy guard."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts import verify_distribution as guard
from decision_evidence_ledger.envelopes import EvidenceEnvelope, verify_envelope
from decision_evidence_ledger.ledger import verify_chain


class DistributionGuardTests(unittest.TestCase):
    """Exercise directory, wheel-like ZIP, and sdist-like TAR inputs."""

    def write(self, root: Path, name: str, content: str | bytes = "SYNTHETIC\n") -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def assert_code(self, result: guard.ScanResult, code: str) -> None:
        self.assertFalse(result.ok)
        self.assertIn(code, result.codes)

    def test_accepts_compliant_directory_and_exact_documentation_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, ".gitignore")
            self.write(root, "README.md")
            self.write(root, "src/decision_evidence_ledger/__init__.py")
            self.write(root, "docs/LOCAL_RELEASE_GUIDE.md")
            result = guard.scan_path(root)

        self.assertTrue(result.ok, result.codes)
        self.assertEqual(result.findings, ())

    def test_accepts_public_citation_file_in_source_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(
                root,
                "CITATION.cff",
                "cff-version: 1.2.0\n"
                "message: Please cite this software using the metadata below.\n"
                "title: Decision Evidence Ledger\n"
                "type: software\n"
                "authors:\n"
                "  - alias: liver-detox\n"
                "version: 0.1.0\n"
                "license: Apache-2.0\n"
                "abstract: Digest-only local evidence envelopes and lifecycle/chain consistency checks.\n",
            )
            result = guard.scan_path(root)

        self.assertTrue(result.ok, result.codes)

    def test_accepts_public_citation_file_in_sdist(self):
        payload = (
            b"cff-version: 1.2.0\n"
            b"message: Please cite this software using the metadata below.\n"
            b"title: Decision Evidence Ledger\n"
            b"type: software\n"
            b"authors:\n"
            b"  - alias: liver-detox\n"
            b"version: 0.1.0\n"
            b"license: Apache-2.0\n"
            b"abstract: Digest-only local evidence envelopes and lifecycle/chain consistency checks.\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "citation.tar.gz")
            with tarfile.open(archive_path, "w:gz") as archive:
                member = tarfile.TarInfo(
                    "decision_evidence_ledger-0.1.0/CITATION.cff"
                )
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            result = guard.scan_path(archive_path)

        self.assertTrue(result.ok, result.codes)

    def test_repository_examples_are_synthetic_and_form_a_valid_bound_chain(self):
        examples = Path(__file__).parents[1] / "examples"
        payload_names = (
            "SYNTHETIC_assert_payload.json",
            "SYNTHETIC_correct_payload.json",
            "SYNTHETIC_withdraw_payload.json",
        )
        metadata = json.loads((examples / "SYNTHETIC_metadata.json").read_text(encoding="utf-8"))
        events = tuple(
            EvidenceEnvelope.from_dict(json.loads(line))
            for line in (examples / "SYNTHETIC_chain.jsonl").read_text(encoding="utf-8").splitlines()
        )

        self.assertTrue(metadata["SYNTHETIC"])
        self.assertEqual(len(events), len(payload_names))
        self.assertTrue(verify_chain(events).ok)
        for event, payload_name in zip(events, payload_names, strict=True):
            payload_text = (examples / payload_name).read_text(encoding="utf-8")
            payload = json.loads(payload_text)
            self.assertTrue(payload["SYNTHETIC"])
            self.assertTrue(verify_envelope(event, payload=payload, metadata=metadata).ok)

    def test_task_seven_public_files_pass_the_guard_themselves(self):
        project = Path(__file__).parents[1]
        public_names = (
            "examples/README.md",
            "examples/SYNTHETIC_assert_payload.json",
            "examples/SYNTHETIC_chain.jsonl",
            "examples/SYNTHETIC_correct_payload.json",
            "examples/SYNTHETIC_metadata.json",
            "examples/SYNTHETIC_withdraw_payload.json",
            "scripts/__init__.py",
            "scripts/verify_distribution.py",
            "tests/test_distribution_guard.py",
            "tests/test_no_io.py",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in public_names:
                self.write(root, name, (project / name).read_bytes())
            result = guard.scan_path(root)

        self.assertTrue(result.ok, result.codes)

    def test_task_one_provenance_files_are_source_and_sdist_only(self):
        """Catches an allowlist that omits provenance evidence or admits it to wheels."""
        names = (
            "PROVENANCE.json",
            "scripts/verify_provenance.py",
            "tests/test_provenance.py",
        )
        payload = b"SYNTHETIC\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in names:
                self.write(root, name)
            source_result = guard.scan_path(root)

            archive_path = root / "provenance.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                for name in names:
                    member = tarfile.TarInfo(f"decision_evidence_ledger-0.1.0/{name}")
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
            sdist_result = guard.scan_path(archive_path)

        self.assertTrue(source_result.ok, source_result.codes)
        self.assertTrue(sdist_result.ok, sdist_result.codes)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, name in enumerate(names):
                wheel_path = root / f"provenance-{index}.whl"
                with zipfile.ZipFile(wheel_path, "w") as archive:
                    archive.writestr(name, payload)
                with self.subTest(name=name):
                    self.assert_code(guard.scan_path(wheel_path), "NOT_ALLOWLISTED")

    def test_ci_configuration_and_contract_test_are_source_only(self):
        """Catches omission from source policy or accidental sdist/wheel admission."""
        names = (".github/workflows/ci.yml", "tests/test_ci_workflow.py")
        payload = b"SYNTHETIC\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in names:
                self.write(root, name)
            source_result = guard.scan_path(root)

        self.assertTrue(source_result.ok, source_result.codes)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, name in enumerate(names):
                archive_path = root / f"ci-source-only-{index}.tar"
                with tarfile.open(archive_path, "w") as archive:
                    member = tarfile.TarInfo(f"decision_evidence_ledger-0.1.0/{name}")
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                wheel_path = root / f"ci-source-only-{index}.whl"
                with zipfile.ZipFile(wheel_path, "w") as archive:
                    archive.writestr(name, payload)
                with self.subTest(name=name, format="sdist"):
                    self.assert_code(guard.scan_path(archive_path), "NOT_ALLOWLISTED")
                with self.subTest(name=name, format="wheel"):
                    self.assert_code(guard.scan_path(wheel_path), "NOT_ALLOWLISTED")

    def test_source_ignores_only_a_real_root_git_directory(self):
        """Catches Git-shaped files, links, or nested metadata escaping the source scan."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "README.md")
            (root / ".git").mkdir()
            real_root_result = guard.scan_path(root)

            cases = (("file", ".git"), ("symlink", ".git"), ("nested", "docs/.git"))
            results = []
            for index, (kind, name) in enumerate(cases):
                candidate = Path(directory, f"case-{index}")
                candidate.mkdir()
                self.write(candidate, "README.md")
                target = candidate / name
                if kind == "file":
                    target.write_text("SYNTHETIC\n", encoding="utf-8")
                elif kind == "symlink":
                    target.symlink_to(candidate / "README.md")
                else:
                    target.mkdir(parents=True)
                results.append(guard.scan_path(candidate))

        self.assertTrue(real_root_result.ok, real_root_result.codes)
        for result in results:
            self.assertFalse(result.ok)

    def test_source_rejects_sensitive_content_in_all_scanned_bypass_paths(self):
        """Catches exclusions that would hide guide, build, cache, or link content."""
        secret = "sk-" + ("A" * 24)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "docs/LOCAL_RELEASE_GUIDE.md", secret)
            guide_result = guard.scan_path(root)

            build_root = Path(directory, "build")
            self.write(build_root, "docs/build/private.md", secret)
            build_result = guard.scan_path(build_root)

            cache_root = Path(directory, "cache")
            self.write(cache_root, ".github/__pycache__/private.py", secret)
            cache_result = guard.scan_path(cache_root)

            link_root = Path(directory, "link")
            self.write(link_root, "README.md", "SYNTHETIC\n")
            (link_root / "ignored-looking.pyc").symlink_to(link_root / "README.md")
            link_result = guard.scan_path(link_root)

        self.assert_code(guide_result, "POTENTIAL_SECRET")
        self.assertFalse(build_result.ok)
        self.assertFalse(cache_result.ok)
        self.assert_code(link_result, "SYMLINK")

    def test_accepts_compliant_zip_and_tar_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "SYNTHETIC.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("decision_evidence_ledger/__init__.py", "SYNTHETIC = True\n")
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/METADATA",
                    "Name: decision-evidence-ledger\n",
                )
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/top_level.txt",
                    "decision_evidence_ledger\n",
                )
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/licenses/LICENSE",
                    "SYNTHETIC\nhttp://www.apache.org/licenses/\n",
                )
            sdist = root / "SYNTHETIC.tar.gz"
            payload = b"SYNTHETIC\n"
            with tarfile.open(sdist, "w:gz") as archive:
                member = tarfile.TarInfo(
                    "decision_evidence_ledger-0.1.0/README.md"
                )
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))

            wheel_result = guard.scan_path(wheel)
            sdist_result = guard.scan_path(sdist)

        self.assertTrue(wheel_result.ok, wheel_result.codes)
        self.assertTrue(sdist_result.ok, sdist_result.codes)

    def test_accepts_bzip2_and_xz_source_archives_with_the_same_budget(self):
        payload = b"SYNTHETIC\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, mode in enumerate(("w:bz2", "w:xz")):
                archive_path = root / f"compressed-{index}.tar"
                with tarfile.open(archive_path, mode) as archive:
                    member = tarfile.TarInfo(
                        "decision_evidence_ledger-0.1.0/README.md"
                    )
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                with self.subTest(mode=mode):
                    result = guard.scan_path(archive_path)
                    self.assertTrue(result.ok, result.codes)

    def test_source_rejects_wheel_and_generated_sdist_members(self):
        format_specific_names = (
            "decision_evidence_ledger/__init__.py",
            "PKG-INFO",
            "decision_evidence_ledger-0.1.0.dist-info/METADATA",
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, name in enumerate(format_specific_names):
                root = Path(directory, f"case-{index}")
                self.write(root, name)
                with self.subTest(name=name):
                    self.assert_code(guard.scan_path(root), "NOT_ALLOWLISTED")

    def test_wheel_rejects_source_sdist_and_multiple_metadata_roots(self):
        cases = (
            ("README.md", "NOT_ALLOWLISTED"),
            ("PKG-INFO", "NOT_ALLOWLISTED"),
            (
                "decision_evidence_ledger-0.2.0.dist-info/METADATA",
                "INVALID_WHEEL_DIST_INFO",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (extra_name, expected) in enumerate(cases):
                wheel = root / f"case-{index}.whl"
                with zipfile.ZipFile(wheel, "w") as archive:
                    archive.writestr(
                        "decision_evidence_ledger/__init__.py",
                        "SYNTHETIC = True\n",
                    )
                    archive.writestr(
                        "decision_evidence_ledger-0.1.0.dist-info/METADATA",
                        "Name: decision-evidence-ledger\n",
                    )
                    archive.writestr(extra_name, "SYNTHETIC\n")
                with self.subTest(extra_name=extra_name):
                    self.assert_code(guard.scan_path(wheel), expected)

    def test_zip_is_not_reinterpreted_as_a_source_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "sdist-shaped.zip")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "decision_evidence_ledger-0.1.0/README.md",
                    "SYNTHETIC\n",
                )
            result = guard.scan_path(archive_path)

        self.assert_code(result, "NOT_ALLOWLISTED")

    def test_source_archive_requires_one_root_and_sdist_members_only(self):
        cases = (
            ("README.md", "INVALID_SDIST_ROOT"),
            (
                "decision_evidence_ledger-0.1.0/decision_evidence_ledger/__init__.py",
                "NOT_ALLOWLISTED",
            ),
            (
                "decision_evidence_ledger-0.1.0/.gitignore",
                "NOT_ALLOWLISTED",
            ),
            ("decision_evidence_ledger-0.1.0", "INVALID_SDIST_ROOT"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (member_name, expected) in enumerate(cases):
                archive_path = root / f"case-{index}.tar"
                payload = b"SYNTHETIC\n"
                with tarfile.open(archive_path, "w") as archive:
                    member = tarfile.TarInfo(member_name)
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                with self.subTest(member_name=member_name):
                    self.assert_code(guard.scan_path(archive_path), expected)

    def test_source_archive_rejects_multiple_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "multiple-roots.tar")
            payload = b"SYNTHETIC\n"
            with tarfile.open(archive_path, "w") as archive:
                for name in (
                    "decision_evidence_ledger-0.1.0/README.md",
                    "decision_evidence_ledger-0.2.0/LICENSE",
                ):
                    member = tarfile.TarInfo(name)
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
            result = guard.scan_path(archive_path)

        self.assert_code(result, "INVALID_SDIST_ROOT")

    def test_empty_source_archive_has_no_valid_sdist_root(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "empty.tar")
            with tarfile.open(archive_path, "w"):
                pass
            result = guard.scan_path(archive_path)

        self.assert_code(result, "INVALID_SDIST_ROOT")

    def test_wheel_requires_exactly_one_metadata_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            no_metadata = root / "no-metadata.whl"
            with zipfile.ZipFile(no_metadata, "w") as archive:
                archive.writestr(
                    "decision_evidence_ledger/__init__.py",
                    "SYNTHETIC = True\n",
                )
            result = guard.scan_path(no_metadata)

        self.assert_code(result, "INVALID_WHEEL_DIST_INFO")

    def test_rejects_absolute_and_parent_archive_paths(self):
        unsafe_absolute = "/" + "Users" + "/SYNTHETIC/private.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            absolute_zip = root / "absolute.zip"
            with zipfile.ZipFile(absolute_zip, "w") as archive:
                archive.writestr(unsafe_absolute, "SYNTHETIC\n")
            traversal_tar = root / "traversal.tar"
            with tarfile.open(traversal_tar, "w") as archive:
                payload = b"SYNTHETIC\n"
                member = tarfile.TarInfo("../SYNTHETIC.py")
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))

            absolute_result = guard.scan_path(absolute_zip)
            traversal_result = guard.scan_path(traversal_tar)

        self.assert_code(absolute_result, "UNSAFE_ARCHIVE_PATH")
        self.assert_code(traversal_result, "UNSAFE_ARCHIVE_PATH")

    def test_rejects_private_directory_forbidden_extension_and_unlisted_docs(self):
        with tempfile.TemporaryDirectory() as directory:
            private_root = Path(directory, "private")
            self.write(private_root, "data/SYNTHETIC.json")
            private_result = guard.scan_path(private_root)

            extension_root = Path(directory, "extension")
            self.write(extension_root, "SYNTHETIC.csv")
            extension_result = guard.scan_path(extension_root)

            docs_root = Path(directory, "docs")
            self.write(docs_root, "docs/UNLISTED.md")
            docs_result = guard.scan_path(docs_root)

        self.assert_code(private_result, "PRIVATE_DIRECTORY")
        self.assert_code(extension_result, "FORBIDDEN_EXTENSION")
        self.assert_code(docs_result, "NOT_ALLOWLISTED")

    def test_rejects_private_paths_market_ids_secrets_email_and_urls(self):
        private_path = "/" + "Users" + "/SYNTHETIC/private.json"
        market_id = "12" + "34" + "56"
        secret = "sk" + "-" + ("A" * 24)
        email = "synthetic" + "@" + "example.invalid"
        url = "https" + "://" + "example.invalid/private"
        cases = (
            (private_path, "PRIVATE_ABSOLUTE_PATH"),
            (market_id, "MARKET_STYLE_IDENTIFIER"),
            (secret, "POTENTIAL_SECRET"),
            (email, "EMAIL_ADDRESS"),
            (url, "URL"),
            ("quant" + "_" + "research", "PRIVATE_PACKAGE_NAME"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, (marker, expected) in enumerate(cases):
                root = Path(directory, f"case-{index}")
                self.write(root, "README.md", f"SYNTHETIC {marker}\n")
                with self.subTest(expected=expected):
                    self.assert_code(guard.scan_path(root), expected)

    def test_license_allows_only_the_known_public_license_urls(self):
        public_one = "http" + "://" + "www.apache.org/licenses/"
        public_two = public_one + "LICENSE-2.0"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "LICENSE", f"SYNTHETIC\n{public_one}\n{public_two}\n")
            result = guard.scan_path(root)

            unknown_root = Path(directory, "unknown")
            self.write(unknown_root, "LICENSE", public_one + "SYNTHETIC-UNKNOWN\n")
            unknown_result = guard.scan_path(unknown_root)

        self.assertTrue(result.ok, result.codes)
        self.assert_code(unknown_result, "URL")

    def test_rejects_binary_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "README.md", b"SYNTHETIC\x00PRIVATE")
            result = guard.scan_path(root)

        self.assert_code(result, "BINARY_CONTENT")

    def test_rejects_member_count_member_size_and_total_size_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            count_archive = root / "count.zip"
            with zipfile.ZipFile(count_archive, "w") as archive:
                archive.writestr(
                    "decision_evidence_ledger/__init__.py",
                    "SYNTHETIC\n",
                )
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/METADATA",
                    "SYNTHETIC\n",
                )
            with mock.patch.object(guard, "MAX_MEMBERS", 1):
                count_result = guard.scan_path(count_archive)

            size_archive = root / "size.zip"
            with zipfile.ZipFile(size_archive, "w") as archive:
                archive.writestr(
                    "decision_evidence_ledger/__init__.py",
                    "S" * 33,
                )
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/METADATA",
                    "SYNTHETIC\n",
                )
            with mock.patch.object(guard, "MAX_MEMBER_BYTES", 32):
                size_result = guard.scan_path(size_archive)

            total_archive = root / "total.zip"
            with zipfile.ZipFile(total_archive, "w") as archive:
                archive.writestr(
                    "decision_evidence_ledger/__init__.py",
                    "S" * 12,
                )
                archive.writestr(
                    "decision_evidence_ledger/canonical.py",
                    "S" * 12,
                )
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/METADATA",
                    "SYNTHETIC\n",
                )
            with mock.patch.object(guard, "MAX_TOTAL_BYTES", 20):
                total_result = guard.scan_path(total_archive)

        self.assert_code(count_result, "TOO_MANY_MEMBERS")
        self.assert_code(size_result, "MEMBER_TOO_LARGE")
        self.assert_code(total_result, "ARCHIVE_TOO_LARGE")

    def test_tar_member_limit_does_not_eagerly_enumerate_every_member(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "bounded.tar.gz")
            payload = b"SYNTHETIC\n"
            with tarfile.open(archive_path, "w:gz") as archive:
                for name in (
                    "decision_evidence_ledger-0.1.0/README.md",
                    "decision_evidence_ledger-0.1.0/LICENSE",
                ):
                    member = tarfile.TarInfo(name)
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
            with (
                mock.patch.object(guard, "MAX_MEMBERS", 1),
                mock.patch.object(tarfile.TarFile, "getmembers") as getmembers,
            ):
                result = guard.scan_path(archive_path)

        getmembers.assert_not_called()
        self.assert_code(result, "TOO_MANY_MEMBERS")

    def test_tar_scan_skips_unbounded_probe_and_bounds_hidden_pax_data(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "pax-budget.tar.gz")
            payload = b"SYNTHETIC\n"
            with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
                member = tarfile.TarInfo(
                    "decision_evidence_ledger-0.1.0/README.md"
                )
                member.pax_headers = {"comment": "S" * 8192}
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            with (
                mock.patch.object(guard, "MAX_TOTAL_BYTES", 32),
                mock.patch.object(guard, "MAX_MEMBERS", 2),
                mock.patch.object(tarfile, "is_tarfile") as probe,
            ):
                result = guard.scan_path(archive_path)

        probe.assert_not_called()
        self.assert_code(result, "ARCHIVE_TOO_LARGE")

    def test_duplicate_tar_member_cannot_bypass_size_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "duplicate-size.tar")
            with tarfile.open(archive_path, "w") as archive:
                for payload in (b"SYNTHETIC\n", b"S" * 33):
                    member = tarfile.TarInfo(
                        "decision_evidence_ledger-0.1.0/README.md"
                    )
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
            with mock.patch.object(guard, "MAX_MEMBER_BYTES", 32):
                result = guard.scan_path(archive_path)

        self.assert_code(result, "DUPLICATE_ARCHIVE_MEMBER")
        self.assert_code(result, "MEMBER_TOO_LARGE")

    def test_unsupported_tar_member_cannot_bypass_size_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "unsupported-size.tar")
            with tarfile.open(archive_path, "w") as archive:
                payload = b"S" * 33
                member = tarfile.TarInfo(
                    "decision_evidence_ledger-0.1.0/SYNTHETIC-link"
                )
                member.type = tarfile.SYMTYPE
                member.linkname = "SYNTHETIC-target"
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
                control = b"SYNTHETIC\n"
                member = tarfile.TarInfo(
                    "decision_evidence_ledger-0.1.0/README.md"
                )
                member.size = len(control)
                archive.addfile(member, io.BytesIO(control))
            with mock.patch.object(guard, "MAX_MEMBER_BYTES", 32):
                result = guard.scan_path(archive_path)

        self.assert_code(result, "UNSUPPORTED_ARCHIVE_MEMBER")
        self.assert_code(result, "MEMBER_TOO_LARGE")

    def test_unsupported_zip_compression_is_reported_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "unsupported.zip")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "decision_evidence_ledger/__init__.py",
                    "SYNTHETIC\n",
                )
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/METADATA",
                    "SYNTHETIC\n",
                )
            contents = bytearray(archive_path.read_bytes())
            local_header = contents.index(b"PK\x03\x04")
            central_header = contents.index(b"PK\x01\x02")
            contents[local_header + 8 : local_header + 10] = (99).to_bytes(2, "little")
            contents[central_header + 10 : central_header + 12] = (99).to_bytes(2, "little")
            archive_path.write_bytes(contents)
            try:
                result = guard.scan_path(archive_path)
            except NotImplementedError:
                self.fail("unsupported ZIP compression escaped fail-closed reporting")

        self.assert_code(result, "READ_ERROR")

    def test_unsupported_zip_required_version_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "future-version.whl")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "decision_evidence_ledger/__init__.py",
                    "SYNTHETIC\n",
                )
                archive.writestr(
                    "decision_evidence_ledger-0.1.0.dist-info/METADATA",
                    "SYNTHETIC\n",
                )
            contents = bytearray(archive_path.read_bytes())
            central_header = contents.index(b"PK\x01\x02")
            contents[central_header + 6 : central_header + 8] = (999).to_bytes(
                2,
                "little",
            )
            archive_path.write_bytes(contents)
            try:
                result = guard.scan_path(archive_path)
            except NotImplementedError:
                self.fail("unsupported ZIP version escaped fail-closed reporting")

        self.assert_code(result, "ARCHIVE_ERROR")

    def test_archive_physical_size_is_bounded_before_format_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "oversized.bin")
            archive_path.write_bytes(b"SYNTHETIC")
            with mock.patch.object(guard, "MAX_ARCHIVE_BYTES", 8, create=True):
                result = guard.scan_path(archive_path)

        self.assert_code(result, "ARCHIVE_TOO_LARGE")

    def test_zip_member_limit_is_checked_before_full_zipinfo_materialization(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory, "member-preflight.zip")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("README.md", "SYNTHETIC\n")
                archive.writestr("LICENSE", "SYNTHETIC\n")
            with (
                mock.patch.object(guard, "MAX_MEMBERS", 1),
                mock.patch.object(
                    guard,
                    "_scan_zip",
                    side_effect=AssertionError("full ZIP parser was reached"),
                ),
            ):
                try:
                    result = guard.scan_path(archive_path)
                except AssertionError:
                    self.fail("ZIP member limit was enforced after full parsing")

        self.assert_code(result, "TOO_MANY_MEMBERS")

    def test_rejects_development_notes_instead_of_silently_excluding_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "progress.md")
            self.write(root, "task-7-report.md")
            result = guard.scan_path(root)

        self.assert_code(result, "NOT_ALLOWLISTED")

    def test_cli_report_never_echoes_sensitive_path_or_content(self):
        marker = "SYNTHETIC-PRIVATE-MARKER-" + ("Z" * 17)
        unsafe_path = "/" + "home" + f"/{marker}"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "README.md", f"{unsafe_path}\n")
            stream = io.StringIO()
            with redirect_stdout(stream):
                status = guard.main([str(root)])
            output = stream.getvalue()
            value = json.loads(output)

        self.assertEqual(status, 2)
        self.assertFalse(value["ok"])
        self.assertNotIn(marker, output)
        self.assertNotIn(unsafe_path, output)
        self.assertEqual(output.count("\n"), 1)
        self.assertTrue(all(set(item) == {"code", "member"} for item in value["findings"]))

    def test_member_labels_are_not_reusable_hashes_of_private_names(self):
        private_name = "/" + "Users" + "/SYNTHETIC/private.json"
        reusable_hash = "member-" + hashlib.sha256(private_name.encode()).hexdigest()[:12]
        first = guard._Collector()
        first.add("CODE_ONE", private_name)
        first.add("CODE_TWO", private_name)
        second = guard._Collector()
        second.add("CODE_ONE", private_name)

        first_labels = {finding.member for finding in first.result().findings}
        second_label = second.result().findings[0].member

        self.assertEqual(len(first_labels), 1)
        self.assertRegex(next(iter(first_labels)), r"^member-[0-9a-f]{32}$")
        self.assertNotIn(reusable_hash, first_labels)
        self.assertNotIn(second_label, first_labels)

    def test_invalid_guard_arguments_are_one_safe_json_line(self):
        marker = "SYNTHETIC-PRIVATE-ARGUMENT-" + ("Q" * 17)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = guard.main(["README.md", marker])

        output = stdout.getvalue()
        self.assertEqual(status, 2)
        self.assertNotEqual(output, "")
        self.assertEqual(
            json.loads(output),
            {"codes": ["INVALID_ARGUMENTS"], "ok": False},
        )
        self.assertEqual(output.count("\n"), 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn(marker, output)

    def test_nonzero_parser_exit_is_also_one_safe_json_line(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(guard._SafeParser, "parse_args", side_effect=SystemExit(2)),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            status = guard.main(["SYNTHETIC"])

        self.assertEqual(status, 2)
        self.assertNotEqual(stdout.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {"codes": ["INVALID_ARGUMENTS"], "ok": False},
        )
        self.assertEqual(stdout.getvalue().count("\n"), 1)
        self.assertEqual(stderr.getvalue(), "")

    def test_safe_parser_disables_long_option_abbreviations_by_default(self):
        parser = guard._SafeParser(add_help=False)
        parser.add_argument("--synthetic-option", action="store_true")

        with self.assertRaises(guard._ArgumentFailure):
            parser.parse_args(["--synthetic"])


if __name__ == "__main__":
    unittest.main()
