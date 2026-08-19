"""Contract tests for digest-only evidence envelopes."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import unittest

from decision_evidence_ledger.envelopes import (
    EvidenceEnvelope,
    seal_envelope,
    verify_envelope,
)


RECORDED_AT = datetime(2026, 1, 2, 3, 4, 5, 6007, tzinfo=timezone.utc)
IDENTIFIERS = {
    "event_id": "evt-01",
    "event_type": "recorded",
    "subject_id": "subject-01",
    "operation": "create",
}


def seal(*, payload=None, metadata=None, **changes):
    """Create one valid envelope with generic JSON fixtures."""
    fields = {**IDENTIFIERS, **changes}
    return seal_envelope(
        **fields,
        recorded_at=RECORDED_AT,
        payload=payload,
        metadata=metadata,
    )


class EvidenceEnvelopeTests(unittest.TestCase):
    """Ensure envelopes expose only bindings and safely verify them."""

    def test_sealed_envelope_exposes_digests_without_payload_or_metadata(self):
        """Fails if sealing retains any source evidence instead of its bindings."""
        envelope = seal(payload={"a": 1}, metadata={"b": True})

        value = envelope.to_dict()
        self.assertIn("payload_sha256", value)
        self.assertIn("metadata_sha256", value)
        self.assertNotIn("payload", value)
        self.assertNotIn("metadata", value)
        self.assertNotIn("payload", envelope.__dataclass_fields__)
        self.assertNotIn("metadata", envelope.__dataclass_fields__)

    def test_identical_semantic_input_has_exact_deterministic_digest(self):
        """Fails if any field binding changes its canonical envelope digest."""
        envelope = seal(payload={"a": 1}, metadata={"b": True})

        self.assertEqual(
            envelope.envelope_sha256,
            "ed1f2c52d451c0240550895fa771c96c524b3aa9c53c72fe82341df68a21050a",
        )

    def test_mapping_order_and_unicode_normalization_keep_hashes_identical(self):
        """Fails if equivalent JSON evidence seals into different bindings."""
        first = seal(payload={"z": "caf\u00e9", "\u00e9": ["\u00e9"]}, metadata={"b": 2, "a": 1})
        second = seal(payload={"e\u0301": ["e\u0301"], "z": "cafe\u0301"}, metadata={"a": 1, "b": 2})

        self.assertEqual(first.payload_sha256, second.payload_sha256)
        self.assertEqual(first.metadata_sha256, second.metadata_sha256)
        self.assertEqual(first.envelope_sha256, second.envelope_sha256)

    def test_changed_payload_is_detected_separately_from_metadata(self):
        """Fails if payload binding is skipped or reported as metadata mismatch."""
        envelope = seal(payload={"a": 1}, metadata={"b": 2})

        result = verify_envelope(envelope, payload={"a": 2}, metadata={"b": 2})

        self.assertEqual(result.codes, ("PAYLOAD_DIGEST_MISMATCH",))

    def test_changed_metadata_is_detected_separately_from_payload(self):
        """Fails if metadata binding is skipped or reported as payload mismatch."""
        envelope = seal(payload={"a": 1}, metadata={"b": 2})

        result = verify_envelope(envelope, payload={"a": 1}, metadata={"b": 3})

        self.assertEqual(result.codes, ("METADATA_DIGEST_MISMATCH",))

    def test_explicit_none_payload_is_checked_as_a_real_json_value(self):
        """Fails if None is confused with an omitted payload verification."""
        envelope = seal(payload=None, metadata={"a": 1})

        self.assertTrue(verify_envelope(envelope, payload=None).ok)
        self.assertEqual(
            verify_envelope(envelope, payload={"a": 1}).codes,
            ("PAYLOAD_DIGEST_MISMATCH",),
        )

    def test_omitted_payload_and_metadata_only_check_self_consistency(self):
        """Fails if absent verification values incorrectly assert bindings."""
        envelope = seal(payload={"a": 1}, metadata={"b": 2})

        self.assertTrue(verify_envelope(envelope).ok)

    def test_envelope_is_immutable(self):
        """Fails if a sealed evidence record can be altered in place."""
        envelope = seal()

        with self.assertRaises(FrozenInstanceError):
            envelope.event_id = "evt-02"

    def test_sealing_rejects_invalid_identifiers_and_previous_digest(self):
        """Fails if invalid opaque identity or chain input is accepted."""
        for name, value in (("event_id", "1invalid"), ("event_type", "bad space"), ("subject_id", ""), ("operation", "x" * 129), ("previous_envelope_sha256", "A" * 64)):
            with self.subTest(name=name):
                with self.assertRaises((TypeError, ValueError)):
                    seal(**{name: value})

    def test_sealing_rejects_naive_timestamps(self):
        """Fails if a timezone-ambiguous evidence time is accepted."""
        with self.assertRaises((TypeError, ValueError)):
            seal_envelope(
                **IDENTIFIERS,
                recorded_at=datetime(2026, 1, 2, 3, 4, 5),
                payload=None,
                metadata=None,
            )

    def test_from_dict_requires_the_exact_public_shape_and_types(self):
        """Fails if deserialization admits omitted, extra, or wrong-typed fields."""
        value = seal().to_dict()
        missing = dict(value)
        missing.pop("operation")
        extra = {**value, "extra": "x"}
        wrong_required = {**value, "event_id": None}
        wrong_optional = {**value, "supersedes_event_id": 1}

        for invalid in (missing, extra, wrong_required, wrong_optional):
            with self.subTest(invalid=invalid.keys()):
                with self.assertRaises((TypeError, ValueError)):
                    EvidenceEnvelope.from_dict(invalid)

    def test_tampering_returns_sorted_unique_codes_without_raising(self):
        """Fails if malformed fields raise or verification misses required defects."""
        envelope = seal()
        tampered = replace(
            envelope,
            schema_version="wrong",
            event_id="1invalid",
            recorded_at="not-a-time",
            payload_sha256="BAD",
            metadata_sha256="also-bad",
            previous_envelope_sha256="bad",
            envelope_sha256="bad",
        )

        result = verify_envelope(tampered)

        self.assertFalse(result.ok)
        self.assertEqual(
            result.codes,
            tuple(sorted({
                "ENVELOPE_DIGEST_MISMATCH",
                "INVALID_DIGEST_FORMAT",
                "INVALID_IDENTIFIER",
                "INVALID_SCHEMA_VERSION",
                "INVALID_TIMESTAMP",
            })),
        )

    def test_tampered_non_self_field_causes_digest_mismatch(self):
        """Fails if an envelope digest does not bind all non-self fields."""
        envelope = replace(seal(), operation="replace")

        self.assertEqual(
            verify_envelope(envelope).codes,
            ("ENVELOPE_DIGEST_MISMATCH",),
        )

    def test_inputs_are_not_mutated(self):
        """Fails if sealing normalizes caller-owned nested JSON in place."""
        payload = {"e\u0301": [{"z": 1, "a": 2}]}
        metadata = {"outer": ["cafe\u0301"]}
        payload_before = {"e\u0301": [{"z": 1, "a": 2}]}
        metadata_before = {"outer": ["cafe\u0301"]}

        seal(payload=payload, metadata=metadata)

        self.assertEqual(payload, payload_before)
        self.assertEqual(metadata, metadata_before)
