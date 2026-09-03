"""Fail-closed privacy checks for a source tree, wheel, or source archive."""

from __future__ import annotations

import argparse
import bz2
from contextlib import contextmanager
from dataclasses import dataclass
import gzip
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import struct
import tarfile
from typing import BinaryIO, Iterator, Literal
import zipfile


MAX_MEMBERS = 512
MAX_MEMBER_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024


_SOURCE_ALLOWED_FILES = frozenset(
    {
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
        ".github/workflows/ci.yml",
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
        "tests/test_cli.py",
        "tests/test_ci_workflow.py",
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

_WHEEL_PACKAGE_FILES = frozenset(
    {
        "decision_evidence_ledger/__init__.py",
        "decision_evidence_ledger/canonical.py",
        "decision_evidence_ledger/cli.py",
        "decision_evidence_ledger/envelopes.py",
        "decision_evidence_ledger/events.py",
        "decision_evidence_ledger/ledger.py",
    }
)

_GENERATED_SDIST_FILES = frozenset(
    {
        "PKG-INFO",
        "setup.cfg",
        "src/decision_evidence_ledger.egg-info/PKG-INFO",
        "src/decision_evidence_ledger.egg-info/SOURCES.txt",
        "src/decision_evidence_ledger.egg-info/dependency_links.txt",
        "src/decision_evidence_ledger.egg-info/entry_points.txt",
        "src/decision_evidence_ledger.egg-info/top_level.txt",
    }
)

_SOURCE_ONLY_FILES = frozenset(
    {
        ".github/workflows/ci.yml",
        ".gitignore",
        "docs/LOCAL_RELEASE_GUIDE.md",
        "tests/test_ci_workflow.py",
    }
)

_SDIST_ALLOWED_FILES = frozenset(
    (_SOURCE_ALLOWED_FILES - _SOURCE_ONLY_FILES) | _GENERATED_SDIST_FILES
)

_SOURCE_ALLOWED_DIRECTORIES = frozenset(
    {
        "docs",
        ".github",
        ".github/workflows",
        "examples",
        "scripts",
        "src",
        "src/decision_evidence_ledger",
        "tests",
    }
)

_SDIST_ALLOWED_DIRECTORIES = frozenset(
    (_SOURCE_ALLOWED_DIRECTORIES - {"docs", ".github", ".github/workflows"})
    | {"src/decision_evidence_ledger.egg-info"}
)

_WHEEL_ALLOWED_DIRECTORIES = frozenset({"decision_evidence_ledger"})

_PRIVATE_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        "archive",
        "archives",
        "build",
        "cache",
        "caches",
        "data",
        "dataset",
        "datasets",
        "dist",
        "handoff",
        "handoffs",
        "log",
        "logs",
        "report",
        "reports",
    }
)

_FORBIDDEN_EXTENSIONS = frozenset(
    {
        ".arrow",
        ".csv",
        ".db",
        ".feather",
        ".gif",
        ".html",
        ".jpeg",
        ".jpg",
        ".log",
        ".parquet",
        ".pdf",
        ".pickle",
        ".pkl",
        ".png",
        ".pyc",
        ".sqlite",
        ".sqlite3",
        ".tsv",
        ".xls",
        ".xlsm",
        ".xlsx",
    }
)

_DIST_INFO_RE = re.compile(
    r"^decision_evidence_ledger-[A-Za-z0-9_.+!-]+\.dist-info$"
)
_SDIST_PREFIX_RE = re.compile(
    r"^decision[-_]evidence[-_]ledger-[0-9][A-Za-z0-9_.+!-]*$"
)
_WHEEL_METADATA_FILES = frozenset(
    {
        "METADATA",
        "RECORD",
        "WHEEL",
        "entry_points.txt",
        "licenses/LICENSE",
        "top_level.txt",
    }
)

_ZIP_EOCD = struct.Struct("<4s4H2LH")
_ZIP_CENTRAL_HEADER = struct.Struct("<4s6H3L5H2L")
_ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
_ZIP_CENTRAL_SIGNATURE = b"PK\x01\x02"
_ZIP_MAX_EOCD_SEARCH = _ZIP_EOCD.size + 65535

_PRIVATE_ROOTS = (
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "C:" + "\\" + "Users" + "\\",
)
_PRIVATE_PACKAGE = "quant" + "_" + "research"
_APACHE_LICENSE_ROOT = "http" + "://" + "www.apache.org/licenses/"
_ALLOWED_LICENSE_URLS = frozenset(
    {_APACHE_LICENSE_ROOT, _APACHE_LICENSE_ROOT + "LICENSE-2.0"}
)
_LOCAL_ENDPOINT = "local" + "host"
_LOOPBACK_ENDPOINT = "127" + r"\.0\.0\.1"
_PRIVATE_NETWORK = "10" + r"\.[0-9]{1,3}(?:\.[0-9]{1,3}){2}"

_CONTENT_RULES = (
    (
        "PRIVATE_ABSOLUTE_PATH",
        re.compile("|".join(re.escape(value) for value in _PRIVATE_ROOTS), re.IGNORECASE),
    ),
    (
        "PRIVATE_PACKAGE_NAME",
        re.compile(r"(?<![A-Za-z0-9_])" + re.escape(_PRIVATE_PACKAGE) + r"(?![A-Za-z0-9_])"),
    ),
    (
        "MARKET_STYLE_IDENTIFIER",
        re.compile(r"(?<![A-Za-z0-9])[0-9]{6}(?![A-Za-z0-9])"),
    ),
    (
        "EMAIL_ADDRESS",
        re.compile(
            r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"
        ),
    ),
    (
        "URL",
        re.compile(r"\bhttps?://[^\s<>'\"`]+", re.IGNORECASE),
    ),
    (
        "PRIVATE_ENDPOINT",
        re.compile(
            r"(?<![A-Za-z0-9])(?:"
            + re.escape(_LOCAL_ENDPOINT)
            + r"(?::[0-9]{2,5})?|"
            + _LOOPBACK_ENDPOINT
            + "|"
            + _PRIVATE_NETWORK
            + r")(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
)

_SECRET_RULES = (
    re.compile("AKIA" + r"[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)"
        r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"
    ),
)


@dataclass(frozen=True, slots=True, order=True)
class Finding:
    """One safe diagnostic with an opaque member label."""

    code: str
    member: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Immutable result of a complete fail-closed scan."""

    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(sorted({finding.code for finding in self.findings}))


class _Collector:
    def __init__(self) -> None:
        self._findings: set[Finding] = set()
        self._member_labels: dict[str, str] = {}
        self._issued_labels: set[str] = set()

    def add(self, code: str, name: str) -> None:
        label = self._member_labels.get(name)
        if label is None:
            while True:
                label = "member-" + secrets.token_hex(16)
                if label not in self._issued_labels:
                    break
            self._member_labels[name] = label
            self._issued_labels.add(label)
        self._findings.add(Finding(code, label))

    def result(self) -> ScanResult:
        return ScanResult(tuple(sorted(self._findings)))


class _ArgumentFailure(Exception):
    """Raised instead of allowing argparse to echo an unsafe argument."""


class _SafeParser(argparse.ArgumentParser):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        raise _ArgumentFailure from None

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if status:
            raise _ArgumentFailure from None
        super().exit(status, message)


class _ArchiveLimitExceeded(Exception):
    """Raised when decompressed TAR input exceeds its fixed budget."""


class _BoundedReader:
    def __init__(self, stream: BinaryIO, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._consumed = 0

    def read(self, size: int = -1) -> bytes:
        remaining = self._limit - self._consumed
        request = remaining + 1
        if size >= 0:
            request = min(size, request)
        contents = self._stream.read(request)
        self._consumed += len(contents)
        if self._consumed > self._limit:
            raise _ArchiveLimitExceeded from None
        return contents


def _tar_stream_budget() -> int:
    return MAX_TOTAL_BYTES + (MAX_MEMBERS * 1024) + 2048


@contextmanager
def _bounded_tar_stream(path: Path) -> Iterator[_BoundedReader]:
    with path.open("rb") as raw:
        magic = raw.read(6)
        raw.seek(0)
        if magic.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=raw, mode="rb") as decoded:
                yield _BoundedReader(decoded, _tar_stream_budget())
        elif magic.startswith(b"BZh"):
            with bz2.BZ2File(raw, mode="rb") as decoded:
                yield _BoundedReader(decoded, _tar_stream_budget())
        elif magic.startswith(b"\xfd7zXZ\x00"):
            with lzma.LZMAFile(raw, mode="rb") as decoded:
                yield _BoundedReader(decoded, _tar_stream_budget())
        else:
            yield _BoundedReader(raw, _tar_stream_budget())


def _path_parts(name: str) -> tuple[str, ...]:
    return PurePosixPath(name).parts


def _has_private_directory(name: str) -> bool:
    return any(part.casefold() in _PRIVATE_DIRECTORY_NAMES for part in _path_parts(name))


def _has_forbidden_extension(name: str) -> bool:
    return PurePosixPath(name).suffix.casefold() in _FORBIDDEN_EXTENSIONS


ArtifactKind = Literal["source", "wheel", "sdist"]


def _is_allowed_directory(
    name: str,
    *,
    kind: ArtifactKind,
    dist_info_root: str | None = None,
) -> bool:
    if not name:
        return True
    if kind == "source":
        return name in _SOURCE_ALLOWED_DIRECTORIES
    if kind == "sdist":
        return name in _SDIST_ALLOWED_DIRECTORIES
    return name in _WHEEL_ALLOWED_DIRECTORIES or (
        dist_info_root is not None
        and name in {dist_info_root, f"{dist_info_root}/licenses"}
    )


def _is_allowed_file(
    name: str,
    *,
    kind: ArtifactKind,
    dist_info_root: str | None = None,
) -> bool:
    if kind == "source":
        return name in _SOURCE_ALLOWED_FILES
    if kind == "sdist":
        return name in _SDIST_ALLOWED_FILES
    if name in _WHEEL_PACKAGE_FILES:
        return True
    parts = _path_parts(name)
    if len(parts) < 2 or dist_info_root is None or parts[0] != dist_info_root:
        return False
    remainder = "/".join(parts[1:])
    return remainder in _WHEEL_METADATA_FILES


def _scan_content(contents: bytes, logical_name: str, reported_name: str, collector: _Collector) -> None:
    if b"\x00" in contents:
        collector.add("BINARY_CONTENT", reported_name)
        return
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        collector.add("BINARY_CONTENT", reported_name)
        return

    parts = _path_parts(logical_name)
    is_wheel_project_license = (
        len(parts) == 3
        and _DIST_INFO_RE.fullmatch(parts[0]) is not None
        and parts[1:] == ("licenses", "LICENSE")
    )
    if logical_name == "LICENSE" or is_wheel_project_license:
        url_pattern = next(pattern for code, pattern in _CONTENT_RULES if code == "URL")
        text = url_pattern.sub(
            lambda match: "" if match.group(0) in _ALLOWED_LICENSE_URLS else match.group(0),
            text,
        )

    for code, pattern in _CONTENT_RULES:
        if pattern.search(text):
            collector.add(code, reported_name)
    if any(pattern.search(text) for pattern in _SECRET_RULES):
        collector.add("POTENTIAL_SECRET", reported_name)


def _screen_logical_name(
    name: str,
    reported_name: str,
    collector: _Collector,
    *,
    kind: ArtifactKind,
    dist_info_root: str | None = None,
) -> bool:
    accepted = True
    if _has_private_directory(name):
        collector.add("PRIVATE_DIRECTORY", reported_name)
        accepted = False
    if _has_forbidden_extension(name):
        collector.add("FORBIDDEN_EXTENSION", reported_name)
        accepted = False
    if not _is_allowed_file(name, kind=kind, dist_info_root=dist_info_root):
        collector.add("NOT_ALLOWLISTED", reported_name)
        accepted = False
    return accepted


def _scan_directory(root: Path) -> ScanResult:
    collector = _Collector()
    if root.is_symlink():
        collector.add("SYMLINK", str(root))
        return collector.result()

    member_count = 0
    total_size = 0
    try:
        for current, directory_names, file_names in os.walk(root, followlinks=False):
            current_path = Path(current)
            kept_directories: list[str] = []
            for directory_name in sorted(directory_names):
                path = current_path / directory_name
                relative = path.relative_to(root).as_posix()
                if relative == ".git" and path.is_dir() and not path.is_symlink():
                    continue
                member_count += 1
                if member_count > MAX_MEMBERS:
                    collector.add("TOO_MANY_MEMBERS", relative)
                    continue
                if path.is_symlink():
                    collector.add("SYMLINK", relative)
                    continue
                if _has_private_directory(relative):
                    collector.add("PRIVATE_DIRECTORY", relative)
                    continue
                if not _is_allowed_directory(relative, kind="source"):
                    collector.add("NOT_ALLOWLISTED", relative)
                    continue
                kept_directories.append(directory_name)
            directory_names[:] = kept_directories

            for file_name in sorted(file_names):
                path = current_path / file_name
                relative = path.relative_to(root).as_posix()
                member_count += 1
                if member_count > MAX_MEMBERS:
                    collector.add("TOO_MANY_MEMBERS", relative)
                    continue
                if path.is_symlink():
                    collector.add("SYMLINK", relative)
                    continue
                if not _screen_logical_name(
                    relative,
                    relative,
                    collector,
                    kind="source",
                ):
                    continue
                try:
                    size = path.stat().st_size
                    total_size += size
                    if size > MAX_MEMBER_BYTES:
                        collector.add("MEMBER_TOO_LARGE", relative)
                        continue
                    if total_size > MAX_TOTAL_BYTES:
                        collector.add("ARCHIVE_TOO_LARGE", relative)
                        continue
                    contents = path.read_bytes()
                except OSError:
                    collector.add("READ_ERROR", relative)
                    continue
                if len(contents) > MAX_MEMBER_BYTES:
                    collector.add("MEMBER_TOO_LARGE", relative)
                    continue
                _scan_content(contents, relative, relative, collector)
    except OSError:
        collector.add("READ_ERROR", str(root))
    return collector.result()


def _valid_archive_name(name: str) -> bool:
    candidate = name[:-1] if name.endswith("/") else name
    if not candidate or "\x00" in candidate or "\\" in candidate:
        return False
    if candidate.startswith("/") or re.match(r"^[A-Za-z]:", candidate):
        return False
    raw_parts = candidate.split("/")
    return all(part not in ("", ".", "..") for part in raw_parts)


def _logical_archive_name(name: str, prefix: str | None) -> str:
    candidate = name[:-1] if name.endswith("/") else name
    if prefix is None:
        return candidate
    if candidate == prefix:
        return ""
    return candidate[len(prefix) + 1 :]


def _screen_archive_name(
    raw_name: str,
    logical_name: str,
    *,
    is_directory: bool,
    kind: ArtifactKind,
    dist_info_root: str | None = None,
    collector: _Collector,
) -> bool:
    if not _valid_archive_name(raw_name):
        collector.add("UNSAFE_ARCHIVE_PATH", raw_name)
        return False
    if not logical_name:
        return is_directory
    if _has_private_directory(logical_name):
        collector.add("PRIVATE_DIRECTORY", raw_name)
        return False
    if is_directory:
        if not _is_allowed_directory(
            logical_name,
            kind=kind,
            dist_info_root=dist_info_root,
        ):
            collector.add("NOT_ALLOWLISTED", raw_name)
            return False
        return True
    return _screen_logical_name(
        logical_name,
        raw_name,
        collector,
        kind=kind,
        dist_info_root=dist_info_root,
    )


def _wheel_dist_info_root(
    names: tuple[str, ...],
    collector: _Collector,
) -> str | None:
    roots = {
        (name[:-1] if name.endswith("/") else name).split("/", 1)[0]
        for name in names
        if _valid_archive_name(name)
        and _DIST_INFO_RE.fullmatch(
            (name[:-1] if name.endswith("/") else name).split("/", 1)[0]
        )
        is not None
    }
    if len(roots) != 1:
        collector.add("INVALID_WHEEL_DIST_INFO", "archive")
        return None
    return next(iter(roots))


def _zip_preflight(path: Path) -> ScanResult | None:
    collector = _Collector()
    try:
        with path.open("rb") as stream:
            file_size = path.stat().st_size
            tail_size = min(file_size, _ZIP_MAX_EOCD_SEARCH)
            stream.seek(file_size - tail_size)
            tail = stream.read(tail_size)
            eocd_index = tail.rfind(_ZIP_EOCD_SIGNATURE)
            if eocd_index < 0 or len(tail) - eocd_index < _ZIP_EOCD.size:
                raise ValueError
            (
                signature,
                disk_number,
                central_disk,
                entries_on_disk,
                declared_entries,
                central_size,
                central_offset,
                comment_size,
            ) = _ZIP_EOCD.unpack_from(tail, eocd_index)
            if signature != _ZIP_EOCD_SIGNATURE:
                raise ValueError
            if eocd_index + _ZIP_EOCD.size + comment_size != len(tail):
                raise ValueError
            if disk_number or central_disk or entries_on_disk != declared_entries:
                raise ValueError
            if declared_entries == 0xFFFF or central_size == 0xFFFFFFFF:
                raise ValueError
            eocd_offset = file_size - tail_size + eocd_index
            if central_offset + central_size != eocd_offset:
                raise ValueError
            if declared_entries > MAX_MEMBERS:
                collector.add("TOO_MANY_MEMBERS", "archive")
                return collector.result()

            stream.seek(central_offset)
            consumed = 0
            counted_entries = 0
            while consumed < central_size:
                header = stream.read(_ZIP_CENTRAL_HEADER.size)
                if len(header) != _ZIP_CENTRAL_HEADER.size:
                    raise ValueError
                fields = _ZIP_CENTRAL_HEADER.unpack(header)
                if fields[0] != _ZIP_CENTRAL_SIGNATURE:
                    raise ValueError
                variable_size = fields[10] + fields[11] + fields[12]
                record_size = _ZIP_CENTRAL_HEADER.size + variable_size
                if record_size > central_size - consumed:
                    raise ValueError
                stream.seek(variable_size, os.SEEK_CUR)
                consumed += record_size
                counted_entries += 1
                if counted_entries > MAX_MEMBERS:
                    collector.add("TOO_MANY_MEMBERS", "archive")
                    return collector.result()
            if consumed != central_size or counted_entries != declared_entries:
                raise ValueError
    except (OSError, struct.error, ValueError):
        collector.add("ARCHIVE_ERROR", str(path))
        return collector.result()
    return None


def _scan_zip(path: Path) -> ScanResult:
    collector = _Collector()
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS:
                collector.add("TOO_MANY_MEMBERS", "archive")
                return collector.result()
            dist_info_root = _wheel_dist_info_root(
                tuple(member.filename for member in members),
                collector,
            )
            declared_total = sum(member.file_size for member in members)
            if declared_total > MAX_TOTAL_BYTES:
                collector.add("ARCHIVE_TOO_LARGE", "archive")
            seen_names: set[str] = set()
            for member in members:
                raw_name = member.filename
                logical_name = _logical_archive_name(raw_name, None)
                if raw_name in seen_names:
                    collector.add("DUPLICATE_ARCHIVE_MEMBER", raw_name)
                    continue
                seen_names.add(raw_name)
                unix_mode = member.external_attr >> 16
                is_symlink = stat.S_ISLNK(unix_mode)
                if is_symlink or member.flag_bits & 1:
                    collector.add("UNSUPPORTED_ARCHIVE_MEMBER", raw_name)
                    continue
                if not _screen_archive_name(
                    raw_name,
                    logical_name,
                    is_directory=member.is_dir(),
                    kind="wheel",
                    dist_info_root=dist_info_root,
                    collector=collector,
                ):
                    continue
                if member.is_dir():
                    continue
                if member.file_size > MAX_MEMBER_BYTES:
                    collector.add("MEMBER_TOO_LARGE", raw_name)
                    continue
                if declared_total > MAX_TOTAL_BYTES:
                    continue
                try:
                    with archive.open(member) as stream:
                        contents = stream.read(MAX_MEMBER_BYTES + 1)
                except (OSError, RuntimeError, zipfile.BadZipFile):
                    collector.add("READ_ERROR", raw_name)
                    continue
                if len(contents) > MAX_MEMBER_BYTES:
                    collector.add("MEMBER_TOO_LARGE", raw_name)
                    continue
                _scan_content(contents, logical_name, raw_name, collector)
    except (OSError, zipfile.BadZipFile, ValueError, NotImplementedError):
        collector.add("ARCHIVE_ERROR", str(path))
    return collector.result()


def _scan_tar(path: Path) -> ScanResult:
    collector = _Collector()
    try:
        with _bounded_tar_stream(path) as stream, tarfile.open(
            fileobj=stream,
            mode="r|",
        ) as archive:
            member_count = 0
            declared_total = 0
            prefix: str | None = None
            seen_names: set[str] = set()
            for member in archive:
                raw_name = member.name
                member_count += 1
                if member_count > MAX_MEMBERS:
                    collector.add("TOO_MANY_MEMBERS", "archive")
                    return collector.result()
                is_duplicate = raw_name in seen_names
                if is_duplicate:
                    collector.add("DUPLICATE_ARCHIVE_MEMBER", raw_name)
                else:
                    seen_names.add(raw_name)
                is_supported = member.isfile() or member.isdir()
                if not is_supported:
                    collector.add("UNSUPPORTED_ARCHIVE_MEMBER", raw_name)
                if member.size > MAX_MEMBER_BYTES:
                    collector.add("MEMBER_TOO_LARGE", raw_name)
                    return collector.result()
                declared_total += member.size
                if declared_total > MAX_TOTAL_BYTES:
                    collector.add("ARCHIVE_TOO_LARGE", "archive")
                    return collector.result()
                if not is_supported:
                    continue
                if is_duplicate:
                    continue
                if not _valid_archive_name(raw_name):
                    _screen_archive_name(
                        raw_name,
                        raw_name,
                        is_directory=member.isdir(),
                        kind="sdist",
                        collector=collector,
                    )
                    continue
                candidate = raw_name[:-1] if raw_name.endswith("/") else raw_name
                first_part = candidate.split("/", 1)[0]
                if prefix is None:
                    if _SDIST_PREFIX_RE.fullmatch(first_part) is None:
                        collector.add("INVALID_SDIST_ROOT", raw_name)
                    else:
                        prefix = first_part
                elif first_part != prefix:
                    collector.add("INVALID_SDIST_ROOT", raw_name)
                logical_name = (
                    _logical_archive_name(raw_name, prefix)
                    if prefix is not None and first_part == prefix
                    else candidate
                )
                if prefix is not None and candidate == prefix and not member.isdir():
                    collector.add("INVALID_SDIST_ROOT", raw_name)
                    continue
                if not _screen_archive_name(
                    raw_name,
                    logical_name,
                    is_directory=member.isdir(),
                    kind="sdist",
                    collector=collector,
                ):
                    continue
                if member.isdir():
                    continue
                try:
                    stream = archive.extractfile(member)
                    if stream is None:
                        collector.add("READ_ERROR", raw_name)
                        continue
                    with stream:
                        contents = stream.read(MAX_MEMBER_BYTES + 1)
                except (OSError, tarfile.TarError):
                    collector.add("READ_ERROR", raw_name)
                    continue
                if len(contents) > MAX_MEMBER_BYTES:
                    collector.add("MEMBER_TOO_LARGE", raw_name)
                    continue
                _scan_content(contents, logical_name, raw_name, collector)
            if prefix is None:
                collector.add("INVALID_SDIST_ROOT", "archive")
    except _ArchiveLimitExceeded:
        collector.add("ARCHIVE_TOO_LARGE", "archive")
    except (OSError, EOFError, tarfile.TarError, ValueError):
        collector.add("ARCHIVE_ERROR", str(path))
    return collector.result()


def _looks_like_tar(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            prefix = stream.read(1024)
    except OSError:
        return False
    if prefix.startswith((b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00")):
        return True
    if len(prefix) >= 262 and prefix[257:262] == b"ustar":
        return True
    return len(prefix) >= 1024 and not prefix.strip(b"\x00")


def scan_path(path: str | Path) -> ScanResult:
    """Scan a directory, ZIP/wheel, or TAR/sdist without extracting archives."""
    candidate = Path(path)
    if candidate.is_dir():
        return _scan_directory(candidate)
    if candidate.is_file():
        try:
            if candidate.stat().st_size > MAX_ARCHIVE_BYTES:
                collector = _Collector()
                collector.add("ARCHIVE_TOO_LARGE", str(candidate))
                return collector.result()
        except OSError:
            collector = _Collector()
            collector.add("READ_ERROR", str(candidate))
            return collector.result()
        try:
            if zipfile.is_zipfile(candidate):
                preflight = _zip_preflight(candidate)
                if preflight is not None:
                    return preflight
                return _scan_zip(candidate)
            if _looks_like_tar(candidate):
                return _scan_tar(candidate)
        except OSError:
            pass
    collector = _Collector()
    collector.add("UNSUPPORTED_INPUT", str(candidate))
    return collector.result()


def result_document(result: ScanResult) -> dict[str, object]:
    """Return a compact report containing no input names or matched content."""
    return {
        "codes": list(result.codes),
        "finding_count": len(result.findings),
        "findings": [
            {"code": finding.code, "member": finding.member}
            for finding in result.findings
        ],
        "ok": result.ok,
    }


def _invalid_arguments() -> int:
    print(json.dumps({"codes": ["INVALID_ARGUMENTS"], "ok": False}, separators=(",", ":")))
    return 2


def main(argv: list[str] | None = None) -> int:
    """Run the guard and emit exactly one payload-safe JSON line."""
    parser = _SafeParser(prog="verify-distribution", allow_abbrev=False)
    parser.add_argument("path")
    try:
        arguments = parser.parse_args(argv)
    except _ArgumentFailure:
        return _invalid_arguments()
    except SystemExit as error:
        return 0 if error.code == 0 else _invalid_arguments()
    result = scan_path(arguments.path)
    print(json.dumps(result_document(result), sort_keys=True, separators=(",", ":")))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
