"""Append-only verification for ordered evidence envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Sequence

from .envelopes import EvidenceEnvelope, verify_envelope
from .events import validate_event


_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_REPLACEMENT_OPERATIONS = frozenset(("CORRECT", "WITHDRAW"))


@dataclass(frozen=True, slots=True)
class LedgerVerification:
    """The outcome of append-only ledger validation."""

    ok: bool
    codes: tuple[str, ...]
    event_count: int
    head_digest: str | None


def _field(value: object, name: str) -> object:
    """Read an untrusted runtime field without allowing it to escape validation."""
    try:
        return getattr(value, name)
    except Exception:
        return None


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST_RE.fullmatch(value) is not None


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or _TIMESTAMP_RE.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


def _envelope_is_valid(value: object) -> bool:
    try:
        return verify_envelope(value).ok  # type: ignore[arg-type]
    except Exception:
        return False


def _event_is_valid(value: object) -> bool:
    try:
        return validate_event(value).ok  # type: ignore[arg-type]
    except Exception:
        return False


def verify_chain(events: Sequence[EvidenceEnvelope]) -> LedgerVerification:
    """Verify integrity, order, and supersession relationships for a ledger."""
    try:
        entries = tuple(events)
    except Exception:
        return LedgerVerification(False, ("INVALID_LEDGER",), 0, None)

    codes: set[str] = set()
    first_by_id: dict[str, object] = {}
    replaced_target_ids: set[str] = set()
    previous_entry: object | None = None
    previous_timestamp: str | None = None

    for index, entry in enumerate(entries):
        envelope_valid = _envelope_is_valid(entry)
        event_valid = _event_is_valid(entry)
        if not envelope_valid:
            codes.add("INVALID_ENVELOPE")
        if not event_valid:
            codes.add("INVALID_EVENT")

        previous_digest = _field(entry, "previous_envelope_sha256")
        if index == 0:
            if previous_digest is not None:
                codes.add("BROKEN_PREVIOUS_DIGEST")
        else:
            predecessor_digest = _field(previous_entry, "envelope_sha256")
            if (
                not _valid_digest(predecessor_digest)
                or previous_digest != predecessor_digest
            ):
                codes.add("BROKEN_PREVIOUS_DIGEST")

        recorded_at = _field(entry, "recorded_at")
        timestamp_valid = _valid_timestamp(recorded_at)
        if previous_timestamp is not None and timestamp_valid:
            if recorded_at < previous_timestamp:
                codes.add("NON_MONOTONIC_TIMESTAMP")
        if timestamp_valid:
            previous_timestamp = recorded_at
        else:
            previous_timestamp = None

        event_id = _field(entry, "event_id")
        duplicate = isinstance(event_id, str) and event_id in first_by_id
        if duplicate:
            codes.add("DUPLICATE_EVENT_ID")

        operation = _field(entry, "operation")
        target_id = _field(entry, "supersedes_event_id")
        if isinstance(operation, str) and operation in _REPLACEMENT_OPERATIONS and isinstance(target_id, str):
            target = first_by_id.get(target_id)
            if target is None:
                codes.add("SUPERSESSION_TARGET_NOT_FOUND")
            elif (
                _field(entry, "subject_id") != _field(target, "subject_id")
                or _field(entry, "event_type") != _field(target, "event_type")
            ):
                codes.add("SUPERSESSION_SCOPE_MISMATCH")
            elif target_id in replaced_target_ids:
                codes.add("SUPERSESSION_TARGET_ALREADY_REPLACED")
            elif envelope_valid and event_valid and not duplicate:
                replaced_target_ids.add(target_id)

        if not duplicate and isinstance(event_id, str):
            first_by_id[event_id] = entry

        previous_entry = entry

    head_digest = None
    if entries:
        final_digest = _field(entries[-1], "envelope_sha256")
        if _valid_digest(final_digest):
            head_digest = final_digest

    result_codes = tuple(sorted(codes))
    return LedgerVerification(not result_codes, result_codes, len(entries), head_digest)


def append_event(
    events: Sequence[EvidenceEnvelope],
    event: EvidenceEnvelope,
) -> tuple[EvidenceEnvelope, ...]:
    """Return a newly appended valid ledger or raise with its diagnostic codes."""
    try:
        candidate = tuple(events) + (event,)
    except Exception:
        raise ValueError("INVALID_ENVELOPE") from None
    verification = verify_chain(candidate)
    if not verification.ok:
        raise ValueError(", ".join(verification.codes))
    return candidate
