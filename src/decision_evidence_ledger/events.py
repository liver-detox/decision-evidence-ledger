"""Generic lifecycle rules for digest-only evidence events."""

from __future__ import annotations

from datetime import datetime

from .envelopes import EvidenceEnvelope, VerificationResult, seal_envelope


OPERATIONS = ("ASSERT", "CORRECT", "WITHDRAW")


def _lifecycle_codes(event: EvidenceEnvelope) -> set[str]:
    """Return lifecycle-only defect codes without trusting event values."""
    codes: set[str] = set()
    operation = getattr(event, "operation", None)
    supersedes_event_id = getattr(event, "supersedes_event_id", None)
    event_id = getattr(event, "event_id", None)

    if operation not in OPERATIONS:
        codes.add("UNKNOWN_OPERATION")
    if supersedes_event_id is not None and supersedes_event_id == event_id:
        codes.add("INVALID_SUPERSESSION")
    if operation == "ASSERT" and supersedes_event_id is not None:
        codes.add("INVALID_SUPERSESSION")
    if operation in ("CORRECT", "WITHDRAW") and supersedes_event_id is None:
        codes.add("INVALID_SUPERSESSION")
    return codes


def create_event(
    *,
    event_id: str,
    event_type: str,
    subject_id: str,
    operation: str,
    supersedes_event_id: str | None,
    recorded_at: datetime,
    payload: object,
    metadata: object,
    previous_envelope_sha256: str | None,
) -> EvidenceEnvelope:
    """Seal an event after enforcing its generic lifecycle structure."""
    if operation not in OPERATIONS:
        raise ValueError("unknown operation")
    if (
        (operation == "ASSERT" and supersedes_event_id is not None)
        or (operation in ("CORRECT", "WITHDRAW") and supersedes_event_id is None)
        or (supersedes_event_id is not None and supersedes_event_id == event_id)
    ):
        raise ValueError("invalid supersession")
    return seal_envelope(
        event_id=event_id,
        event_type=event_type,
        subject_id=subject_id,
        operation=operation,
        supersedes_event_id=supersedes_event_id,
        recorded_at=recorded_at,
        payload=payload,
        metadata=metadata,
        previous_envelope_sha256=previous_envelope_sha256,
    )


def validate_event(event: EvidenceEnvelope) -> VerificationResult:
    """Validate lifecycle structure without checking ledger-wide constraints."""
    try:
        codes = _lifecycle_codes(event)
    except Exception:
        codes = {"INVALID_SUPERSESSION"}
    result_codes = tuple(sorted(codes))
    return VerificationResult(not result_codes, result_codes)
