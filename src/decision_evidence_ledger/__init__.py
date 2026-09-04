"""Decision Evidence Ledger public package interface."""

__version__ = "0.2.0"

from .envelopes import EvidenceEnvelope, VerificationResult, seal_envelope, verify_envelope
from .events import OPERATIONS, create_event, validate_event
from .ledger import LedgerVerification, append_event, verify_chain

__all__ = [
    "EvidenceEnvelope",
    "VerificationResult",
    "seal_envelope",
    "verify_envelope",
    "OPERATIONS",
    "create_event",
    "validate_event",
    "LedgerVerification",
    "verify_chain",
    "append_event",
]
