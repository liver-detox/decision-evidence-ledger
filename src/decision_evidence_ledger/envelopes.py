"""Immutable digest-only envelopes for canonical JSON evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Mapping

from .canonical import canonical_timestamp, sha256_hex


_SCHEMA_VERSION = "decision-evidence-ledger/v1"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_UNSET = object()


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """The outcome of structural and optional binding verification."""

    ok: bool
    codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    """Public digest-only envelope fields."""

    schema_version: str
    event_id: str
    event_type: str
    subject_id: str
    operation: str
    supersedes_event_id: str | None
    recorded_at: str
    payload_sha256: str
    metadata_sha256: str
    previous_envelope_sha256: str | None
    envelope_sha256: str

    def to_dict(self) -> dict[str, str | None]:
        """Return the complete public envelope representation."""
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "subject_id": self.subject_id,
            "operation": self.operation,
            "supersedes_event_id": self.supersedes_event_id,
            "recorded_at": self.recorded_at,
            "payload_sha256": self.payload_sha256,
            "metadata_sha256": self.metadata_sha256,
            "previous_envelope_sha256": self.previous_envelope_sha256,
            "envelope_sha256": self.envelope_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "EvidenceEnvelope":
        """Load an envelope only when it has the exact public shape."""
        if not isinstance(value, Mapping) or set(value) != set(_PUBLIC_FIELDS):
            raise ValueError("invalid envelope")
        for name in _REQUIRED_STRING_FIELDS:
            if not isinstance(value[name], str):
                raise ValueError("invalid envelope")
        for name in _OPTIONAL_STRING_FIELDS:
            if value[name] is not None and not isinstance(value[name], str):
                raise ValueError("invalid envelope")
        return cls(**value)  # type: ignore[arg-type]


_PUBLIC_FIELDS = (
    "schema_version",
    "event_id",
    "event_type",
    "subject_id",
    "operation",
    "supersedes_event_id",
    "recorded_at",
    "payload_sha256",
    "metadata_sha256",
    "previous_envelope_sha256",
    "envelope_sha256",
)
_NON_SELF_FIELDS = _PUBLIC_FIELDS[:-1]
_REQUIRED_STRING_FIELDS = tuple(
    name for name in _PUBLIC_FIELDS if name not in {"supersedes_event_id", "previous_envelope_sha256"}
)
_OPTIONAL_STRING_FIELDS = ("supersedes_event_id", "previous_envelope_sha256")
_IDENTIFIER_FIELDS = ("event_id", "event_type", "subject_id", "operation")


def _is_identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER_RE.fullmatch(value) is not None


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST_RE.fullmatch(value) is not None


def _is_timestamp(value: object) -> bool:
    if not isinstance(value, str) or _TIMESTAMP_RE.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


def _non_self_dict(envelope: EvidenceEnvelope) -> dict[str, object]:
    return {name: getattr(envelope, name) for name in _NON_SELF_FIELDS}


def _envelope_digest(envelope: EvidenceEnvelope) -> str:
    return sha256_hex(_non_self_dict(envelope))


def _validate_sealing_inputs(
    *,
    event_id: str,
    event_type: str,
    subject_id: str,
    operation: str,
    supersedes_event_id: str | None,
    previous_envelope_sha256: str | None,
) -> None:
    if not all(_is_identifier(value) for value in (event_id, event_type, subject_id, operation)):
        raise ValueError("invalid identifier")
    if supersedes_event_id is not None and not _is_identifier(supersedes_event_id):
        raise ValueError("invalid identifier")
    if previous_envelope_sha256 is not None and not _is_digest(previous_envelope_sha256):
        raise ValueError("invalid digest")


def seal_envelope(
    *,
    event_id: str,
    event_type: str,
    subject_id: str,
    operation: str,
    recorded_at: datetime,
    payload: object,
    metadata: object,
    supersedes_event_id: str | None = None,
    previous_envelope_sha256: str | None = None,
) -> EvidenceEnvelope:
    """Seal canonical JSON bindings without retaining source evidence."""
    _validate_sealing_inputs(
        event_id=event_id,
        event_type=event_type,
        subject_id=subject_id,
        operation=operation,
        supersedes_event_id=supersedes_event_id,
        previous_envelope_sha256=previous_envelope_sha256,
    )
    envelope = EvidenceEnvelope(
        schema_version=_SCHEMA_VERSION,
        event_id=event_id,
        event_type=event_type,
        subject_id=subject_id,
        operation=operation,
        supersedes_event_id=supersedes_event_id,
        recorded_at=canonical_timestamp(recorded_at),
        payload_sha256=sha256_hex(payload),
        metadata_sha256=sha256_hex(metadata),
        previous_envelope_sha256=previous_envelope_sha256,
        envelope_sha256="",
    )
    return EvidenceEnvelope(**_non_self_dict(envelope), envelope_sha256=_envelope_digest(envelope))


def verify_envelope(
    envelope: EvidenceEnvelope,
    *,
    payload: object = _UNSET,
    metadata: object = _UNSET,
) -> VerificationResult:
    """Verify envelope structure and optionally its payload/metadata bindings."""
    codes: set[str] = set()
    try:
        if not isinstance(envelope, EvidenceEnvelope):
            return VerificationResult(False, ("ENVELOPE_DIGEST_MISMATCH",))
        if envelope.schema_version != _SCHEMA_VERSION:
            codes.add("INVALID_SCHEMA_VERSION")
        if not all(_is_identifier(getattr(envelope, name)) for name in _IDENTIFIER_FIELDS):
            codes.add("INVALID_IDENTIFIER")
        if envelope.supersedes_event_id is not None and not _is_identifier(envelope.supersedes_event_id):
            codes.add("INVALID_IDENTIFIER")
        if not _is_timestamp(envelope.recorded_at):
            codes.add("INVALID_TIMESTAMP")
        if not _is_digest(envelope.payload_sha256) or not _is_digest(envelope.metadata_sha256):
            codes.add("INVALID_DIGEST_FORMAT")
        if envelope.previous_envelope_sha256 is not None and not _is_digest(envelope.previous_envelope_sha256):
            codes.add("INVALID_DIGEST_FORMAT")
        if not _is_digest(envelope.envelope_sha256):
            codes.add("INVALID_DIGEST_FORMAT")
        try:
            expected_digest = _envelope_digest(envelope)
        except (TypeError, ValueError):
            expected_digest = None
        if expected_digest != envelope.envelope_sha256:
            codes.add("ENVELOPE_DIGEST_MISMATCH")
        if payload is not _UNSET:
            try:
                if sha256_hex(payload) != envelope.payload_sha256:
                    codes.add("PAYLOAD_DIGEST_MISMATCH")
            except (TypeError, ValueError):
                codes.add("PAYLOAD_DIGEST_MISMATCH")
        if metadata is not _UNSET:
            try:
                if sha256_hex(metadata) != envelope.metadata_sha256:
                    codes.add("METADATA_DIGEST_MISMATCH")
            except (TypeError, ValueError):
                codes.add("METADATA_DIGEST_MISMATCH")
    except Exception:
        codes.add("ENVELOPE_DIGEST_MISMATCH")
    result_codes = tuple(sorted(codes))
    return VerificationResult(not result_codes, result_codes)
