"""Verify the local public-candidate provenance statement fail closed."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import stat
import tarfile
from typing import Sequence
import unicodedata

try:
    from scripts import verify_distribution as _distribution_guard
except ModuleNotFoundError:
    import verify_distribution as _distribution_guard


SCHEMA_VERSION = "decision-evidence-ledger/public-provenance/v1"
CANDIDATE_STATUS = "V0_2_0_GITHUB_SOURCE_RELEASE_AUTHORIZED"
PUBLICATION_AUTHORIZATION = "GRANTED_FOR_GITHUB_V0_2_0_TAG_AND_HOSTED_SOURCE_RELEASE_ONLY"
DECISION = "INCLUDE_IN_LOCAL_PUBLIC_CANDIDATE"
SOURCE_ONLY_PATHS = (
    ".github/workflows/ci.yml",
    ".gitignore",
    "docs/LOCAL_RELEASE_GUIDE.md",
    "tests/test_ci_workflow.py",
)
ORIGINS = frozenset(
    {
        "STANDARD_APACHE_2_0_LICENSE_TEXT",
        "MAINTAINER_CONTROLLED_CLEAN_REWRITE",
        "SYNTHETIC_FIXTURE_CREATED_LOCALLY",
        "LOCAL_AI_ASSISTED_PROJECT_AUTHORING",
    }
)
_MAX_DOCUMENT_BYTES = 1024 * 1024
_ARCHIVE_PREFLIGHT_CODES = frozenset(
    {
        "ARCHIVE_ERROR",
        "ARCHIVE_TOO_LARGE",
        "MEMBER_TOO_LARGE",
        "READ_ERROR",
        "TOO_MANY_MEMBERS",
    }
)

_RUNTIME_PATHS = frozenset(
    {
        "src/decision_evidence_ledger/__init__.py",
        "src/decision_evidence_ledger/canonical.py",
        "src/decision_evidence_ledger/cli.py",
        "src/decision_evidence_ledger/envelopes.py",
        "src/decision_evidence_ledger/events.py",
        "src/decision_evidence_ledger/ledger.py",
    }
)
_SYNTHETIC_PATHS = frozenset(
    {
        "examples/SYNTHETIC_assert_payload.json",
        "examples/SYNTHETIC_chain.jsonl",
        "examples/SYNTHETIC_correct_payload.json",
        "examples/SYNTHETIC_metadata.json",
        "examples/SYNTHETIC_withdraw_payload.json",
    }
)
_EXPECTED_PATHS = frozenset(
    {
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
        *_SYNTHETIC_PATHS,
        "examples/rebuild_synthetic_chain.py",
        "pyproject.toml",
        "scripts/__init__.py",
        "scripts/verify_distribution.py",
        "scripts/verify_provenance.py",
        *_RUNTIME_PATHS,
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
    }
)


@dataclass(frozen=True, slots=True)
class ProvenanceResult:
    ok: bool
    codes: tuple[str, ...]
    documented_count: int
    observed_count: int
    archive_count: int | None


def _result(
    codes: set[str],
    documented_count: int,
    observed_count: int,
    archive_count: int | None = None,
) -> ProvenanceResult:
    return ProvenanceResult(
        ok=not codes,
        codes=tuple(sorted(codes)),
        documented_count=documented_count,
        observed_count=observed_count,
        archive_count=archive_count,
    )


def _origin_for(path: str) -> str:
    if path == "LICENSE":
        return "STANDARD_APACHE_2_0_LICENSE_TEXT"
    if path in _RUNTIME_PATHS:
        return "MAINTAINER_CONTROLLED_CLEAN_REWRITE"
    if path in _SYNTHETIC_PATHS:
        return "SYNTHETIC_FIXTURE_CREATED_LOCALLY"
    return "LOCAL_AI_ASSISTED_PROJECT_AUTHORING"


class _DuplicateKeyError(ValueError):
    """Raised when JSON uses the same object key twice."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _open_root(root: Path) -> tuple[int | None, str | None]:
    try:
        root_status = os.lstat(root)
    except OSError:
        return None, "TREE_READ_ERROR"
    if stat.S_ISLNK(root_status.st_mode):
        return None, "ROOT_SYMLINK_INVALID"
    if not stat.S_ISDIR(root_status.st_mode):
        return None, "TREE_READ_ERROR"
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory is None:
        return None, "TREE_READ_ERROR"
    try:
        descriptor = os.open(root, os.O_RDONLY | no_follow | directory)
    except OSError:
        return None, "TREE_READ_ERROR"
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            return None, "TREE_READ_ERROR"
    except OSError:
        os.close(descriptor)
        return None, "TREE_READ_ERROR"
    return descriptor, None


def _read_document(root_descriptor: int) -> tuple[object | None, str | None]:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        return None, "DOCUMENT_READ_UNSAFE"
    try:
        descriptor = os.open(
            "PROVENANCE.json",
            os.O_RDONLY | no_follow | getattr(os, "O_NONBLOCK", 0),
            dir_fd=root_descriptor,
        )
    except OSError:
        return None, "DOCUMENT_READ_UNSAFE"
    try:
        document_status = os.fstat(descriptor)
        if not stat.S_ISREG(document_status.st_mode) or document_status.st_size > _MAX_DOCUMENT_BYTES:
            return None, "DOCUMENT_READ_UNSAFE"
        handle = os.fdopen(descriptor, "r", encoding="utf-8")
        descriptor = -1
        with handle:
            raw = handle.read()
        return json.loads(raw, object_pairs_hook=_unique_object), None
    except _DuplicateKeyError:
        return None, "DOCUMENT_JSON_DUPLICATE_KEY"
    except (ValueError, RecursionError):
        return None, "DOCUMENT_JSON_INVALID"
    except (OSError, UnicodeError):
        return None, "DOCUMENT_READ_UNSAFE"
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _is_safe_path(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or unicodedata.normalize("NFC", value) != value
    ):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in ("", ".", "..") for part in path.parts) and path.as_posix() == value


def _observe(root: Path) -> tuple[set[str], set[str]]:
    observed: set[str] = set()
    codes: set[str] = set()

    def walk(directory: Path, prefix: str) -> None:
        try:
            entries = tuple(os.scandir(directory))
        except OSError:
            codes.add("TREE_READ_ERROR")
            return
        for entry in entries:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                if entry.name == ".git":
                    if not prefix and entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                        continue
                    codes.add("ROOT_GIT_INVALID" if not prefix else "NESTED_GIT_INVALID")
                elif entry.is_symlink():
                    codes.add("TREE_SYMLINK_INVALID")
                elif entry.is_dir(follow_symlinks=False):
                    walk(Path(entry.path), relative)
                elif entry.is_file(follow_symlinks=False):
                    observed.add(relative)
                else:
                    codes.add("TREE_PATH_INVALID")
            except OSError:
                codes.add("TREE_READ_ERROR")

    if root.is_symlink() or not root.is_dir():
        codes.add("TREE_READ_ERROR")
    else:
        walk(root, "")
    return observed, codes


_ARCHIVE_PREFIX = "decision_evidence_ledger-0.2.0"


def _archive_ancestors(paths: set[str]) -> set[str]:
    return {
        "/".join(parts[:index])
        for path in paths
        for parts in [path.split("/")]
        for index in range(1, len(parts))
    }


def _verify_archive(path: Path, expected_files: set[str]) -> tuple[set[str], int]:
    """Validate only safe Git-style TAR members without revealing their names."""
    preflight_codes = set(_distribution_guard.scan_path(path).codes) & _ARCHIVE_PREFLIGHT_CODES
    if preflight_codes:
        return preflight_codes, 0
    codes: set[str] = set()
    observed_files: set[str] = set()
    seen_names: set[str] = set()
    expected_directories = _archive_ancestors(expected_files)
    root_header_seen = False
    try:
        status = os.lstat(path)
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISREG(status.st_mode):
            return {"ARCHIVE_READ_ERROR"}, 0
        with tarfile.open(path, "r:*") as archive:
            for member in archive:
                raw_name = member.name
                name = raw_name[:-1] if raw_name.endswith("/") else raw_name
                if name in seen_names:
                    codes.add("ARCHIVE_DUPLICATE_MEMBER")
                    continue
                seen_names.add(name)
                if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
                    codes.add("ARCHIVE_SPECIAL_MEMBER")
                    continue
                if not _is_safe_path(name):
                    codes.add("ARCHIVE_UNSAFE_PATH")
                    continue
                if name == _ARCHIVE_PREFIX:
                    if not member.isdir():
                        codes.add("ARCHIVE_PREFIX_INVALID")
                    else:
                        root_header_seen = True
                    continue
                if not name.startswith(_ARCHIVE_PREFIX + "/"):
                    codes.add("ARCHIVE_PREFIX_INVALID")
                    continue
                logical_name = name[len(_ARCHIVE_PREFIX) + 1 :]
                if not _is_safe_path(logical_name):
                    codes.add("ARCHIVE_UNSAFE_PATH")
                    continue
                if member.isdir():
                    if logical_name not in expected_directories:
                        codes.add("ARCHIVE_EXTRA_DIRECTORY")
                    continue
                if logical_name in expected_files:
                    observed_files.add(logical_name)
                else:
                    codes.add("ARCHIVE_EXTRA_FILE")
    except (OSError, tarfile.TarError, EOFError):
        return codes | {"ARCHIVE_READ_ERROR"}, len(observed_files)
    if not root_header_seen:
        codes.add("ARCHIVE_PREFIX_INVALID")
    if expected_files - observed_files:
        codes.add("ARCHIVE_MISSING_FILE")
    return codes, len(observed_files)


def verify_tree(root: Path, *, archive_path: Path | None = None) -> ProvenanceResult:
    """Return a stable, path-redacting verdict for one candidate tree."""
    documented_count = 0
    root_descriptor, root_error = _open_root(root)
    if root_error == "ROOT_SYMLINK_INVALID":
        return _result({root_error}, documented_count, 0)
    if root_descriptor is None:
        return _result({"DOCUMENT_JSON_INVALID", root_error or "TREE_READ_ERROR"}, documented_count, 0)
    try:
        observed, codes = _observe(root)
        document, document_error = _read_document(root_descriptor)
    finally:
        os.close(root_descriptor)
    if not isinstance(document, dict):
        codes.add(document_error or "DOCUMENT_SCHEMA_INVALID")
        return _result(codes, documented_count, len(observed))

    if set(document) != {
        "schema_version",
        "candidate_status",
        "publication_authorization",
        "controller",
        "source_only_paths",
        "files",
    }:
        codes.add("DOCUMENT_SCHEMA_INVALID")

    files = document.get("files")
    if isinstance(files, list):
        documented_count = len(files)
    else:
        codes.add("DOCUMENT_SCHEMA_INVALID")
        return _result(codes, documented_count, len(observed))

    controller = document.get("controller")
    expected_controller = {
        "public_alias": "liver-detox",
        "development": "LOCAL_AI_ASSISTED",
        "reported_employer_client_coauthor_contract_claim": False,
        "reported_external_source_code_copy_or_adaptation": False,
    }
    controller_assertion_fields = (
        "reported_employer_client_coauthor_contract_claim",
        "reported_external_source_code_copy_or_adaptation",
    )
    if (
        document.get("schema_version") != SCHEMA_VERSION
        or document.get("candidate_status") != CANDIDATE_STATUS
        or document.get("publication_authorization") != PUBLICATION_AUTHORIZATION
        or not isinstance(controller, dict)
        or any(type(controller.get(field)) is not bool for field in controller_assertion_fields)
        or controller != expected_controller
    ):
        codes.add("DOCUMENT_CONTROLLER_INVALID")

    source_only_paths = document.get("source_only_paths")
    if not isinstance(source_only_paths, list):
        codes.add("SOURCE_ONLY_POLICY_MISSING")
    elif not all(_is_safe_path(path) for path in source_only_paths):
        codes.add("SOURCE_ONLY_UNDOCUMENTED")
    elif len(set(source_only_paths)) != len(source_only_paths):
        codes.add("SOURCE_ONLY_DUPLICATE")
    elif source_only_paths != sorted(source_only_paths):
        codes.add("SOURCE_ONLY_UNSORTED")

    documented: list[str] = []
    origins: dict[str, str] = {}
    decisions: dict[str, object] = {}
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "origin", "decision"}:
            codes.add("DOCUMENT_SCHEMA_INVALID")
            continue
        path = entry.get("path")
        origin = entry.get("origin")
        if not _is_safe_path(path):
            codes.add("DOCUMENT_UNSAFE_PATH")
            continue
        if not isinstance(origin, str):
            codes.add("DOCUMENT_SCHEMA_INVALID")
            continue
        documented.append(path)
        origins[path] = origin
        decisions[path] = entry.get("decision")

    if len(set(documented)) != len(documented):
        codes.add("DOCUMENT_DUPLICATE_PATH")
    if documented != sorted(documented):
        codes.add("DOCUMENT_PATHS_UNSORTED")
    if set(documented) != _EXPECTED_PATHS:
        codes.add("DOCUMENT_PATHS_INVALID")
    if any(origin not in ORIGINS for origin in origins.values()):
        codes.add("DOCUMENT_ORIGIN_INVALID")
    if any(origins.get(path) != _origin_for(path) for path in _EXPECTED_PATHS):
        codes.add("DOCUMENT_MAPPING_INVALID")
    if any(decisions.get(path) != DECISION for path in _EXPECTED_PATHS):
        codes.add("DOCUMENT_DECISION_INVALID")
    if isinstance(source_only_paths, list):
        if any(path not in set(documented) for path in source_only_paths):
            codes.add("SOURCE_ONLY_UNDOCUMENTED")
        elif len(source_only_paths) < len(SOURCE_ONLY_PATHS) and set(source_only_paths) <= set(SOURCE_ONLY_PATHS):
            codes.add("SOURCE_ONLY_POLICY_MISSING")
        elif tuple(source_only_paths) != SOURCE_ONLY_PATHS:
            codes.add("SOURCE_ONLY_RECLASSIFIED")
    missing = set(documented) - observed
    extra = observed - set(documented)
    if missing:
        codes.add("TREE_MISSING_FILE")
    if extra:
        codes.add("TREE_EXTRA_FILE")
    archive_count: int | None = None
    if archive_path is not None:
        archive_codes, archive_count = _verify_archive(
            archive_path, set(documented) - set(SOURCE_ONLY_PATHS)
        )
        codes.update(archive_codes)
    return _result(codes, documented_count, len(observed), archive_count)


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _SafeParser(prog="verify-provenance", allow_abbrev=False, add_help=False)
    parser.add_argument("root", nargs="?")
    parser.add_argument("--archive")
    try:
        arguments = parser.parse_args(argv)
        if arguments.root is None:
            raise ValueError("root is required")
        result = verify_tree(
            Path(arguments.root),
            archive_path=Path(arguments.archive) if arguments.archive is not None else None,
        )
    except (ValueError, OSError):
        result = ProvenanceResult(False, ("CLI_ARGUMENT_ERROR",), 0, 0, None)
    print(json.dumps(asdict(result), sort_keys=True, separators=(",", ":")))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
