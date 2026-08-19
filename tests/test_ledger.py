"""Contract tests for append-only evidence-ledger verification."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from decision_evidence_ledger.canonical import sha256_hex
from decision_evidence_ledger.envelopes import EvidenceEnvelope, seal_envelope
from decision_evidence_ledger.events import create_event
from decision_evidence_ledger.ledger import append_event, verify_chain


BASE_TIME = datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)


def event(
    number: int,
    prior: tuple[EvidenceEnvelope, ...] = (),
    *,
    operation: str = "ASSERT",
    supersedes_event_id: str | None = None,
    subject_id: str = "SYNTHETIC-SUBJECT-A",
    event_type: str = "SYNTHETIC-TYPE-A",
    recorded_at: datetime | None = None,
    event_id: str | None = None,
) -> EvidenceEnvelope:
    """Create a sealed synthetic event linked to the given synthetic chain."""
    return create_event(
        event_id=event_id or f"SYNTHETIC-EVENT-{number}",
        event_type=event_type,
        subject_id=subject_id,
        operation=operation,
        supersedes_event_id=supersedes_event_id,
        recorded_at=recorded_at or BASE_TIME + timedelta(seconds=number),
        payload={"SYNTHETIC": number},
        metadata={"SYNTHETIC": "LEDGER"},
        previous_envelope_sha256=prior[-1].envelope_sha256 if prior else None,
    )


def invalid_lifecycle_event(number: int, prior: tuple[EvidenceEnvelope, ...]) -> EvidenceEnvelope:
    """Make a self-consistent envelope whose lifecycle operation is invalid."""
    return seal_envelope(
        event_id=f"SYNTHETIC-EVENT-{number}",
        event_type="SYNTHETIC-TYPE-A",
        subject_id="SYNTHETIC-SUBJECT-A",
        operation="SYNTHETIC-UNKNOWN",
        recorded_at=BASE_TIME + timedelta(seconds=number),
        payload={"SYNTHETIC": number},
        metadata={"SYNTHETIC": "LEDGER"},
        previous_envelope_sha256=prior[-1].envelope_sha256 if prior else None,
    )


class LedgerVerificationTests(unittest.TestCase):
    """Verify ordered evidence envelopes as an append-only ledger."""

    def test_empty_chain_is_valid_with_no_head(self):
        """Fails if an empty ledger is rejected or advertises a head digest."""
        result = verify_chain(())

        self.assertEqual(result.ok, True)
        self.assertEqual(result.codes, ())
        self.assertEqual(result.event_count, 0)
        self.assertIsNone(result.head_digest)

    def test_non_iterable_or_broken_ledger_input_fails_closed(self):
        """Fails if an unreadable ledger is silently reinterpreted as empty and valid."""

        class BrokenLedger:
            def __iter__(self):
                raise RuntimeError("SYNTHETIC-PRIVATE-MARKER")

        for value in (None, BrokenLedger()):
            with self.subTest(value_type=type(value).__name__):
                result = verify_chain(value)  # type: ignore[arg-type]
                self.assertFalse(result.ok)
                self.assertEqual(result.codes, ("INVALID_LEDGER",))
                self.assertEqual(result.event_count, 0)
                self.assertIsNone(result.head_digest)

    def test_valid_assert_then_correct_chain_is_accepted(self):
        """Fails if a valid correction cannot replace an earlier assertion."""
        first = event(1)
        chain = (first, event(2, (first,), operation="CORRECT", supersedes_event_id=first.event_id))

        result = verify_chain(chain)

        self.assertTrue(result.ok)
        self.assertEqual(result.event_count, 2)
        self.assertEqual(result.head_digest, chain[-1].envelope_sha256)

    def test_valid_assert_then_withdraw_chain_is_accepted(self):
        """Fails if a valid withdrawal cannot replace an earlier assertion."""
        first = event(1)
        chain = (first, event(2, (first,), operation="WITHDRAW", supersedes_event_id=first.event_id))

        self.assertTrue(verify_chain(chain).ok)

    def test_correction_may_correct_a_previous_correction(self):
        """Fails if only assertions, rather than prior events, may be corrected."""
        first = event(1)
        second = event(2, (first,), operation="CORRECT", supersedes_event_id=first.event_id)
        third = event(3, (first, second), operation="CORRECT", supersedes_event_id=second.event_id)

        self.assertTrue(verify_chain((first, second, third)).ok)

    def test_first_event_requires_a_null_previous_digest(self):
        """Fails if a ledger may start after an unrepresented predecessor."""
        invalid_first = event(1, (event(99),))

        self.assertIn("BROKEN_PREVIOUS_DIGEST", verify_chain((invalid_first,)).codes)

    def test_each_event_must_link_to_its_immediate_predecessor(self):
        """Fails if deleted, reordered, or inserted entries do not break the chain."""
        first = event(1)
        second = event(2, (first,))
        third = event(3, (first, second))
        inserted = event(4, (first,))

        for altered in ((second, first), (first, third), (first, inserted, second)):
            with self.subTest(altered=tuple(item.event_id for item in altered)):
                self.assertIn("BROKEN_PREVIOUS_DIGEST", verify_chain(altered).codes)

    def test_tampered_entry_is_reported_as_invalid_envelope(self):
        """Fails if a changed sealed field no longer invalidates its envelope."""
        first = event(1)
        tampered = replace(event(2, (first,)), subject_id="SYNTHETIC-SUBJECT-B")

        self.assertIn("INVALID_ENVELOPE", verify_chain((first, tampered)).codes)

    def test_duplicate_id_does_not_overwrite_first_lookup_entry(self):
        """Fails if a duplicate identifier changes the supersession target lookup."""
        first = event(1, event_id="SYNTHETIC-DUPLICATE")
        duplicate = event(2, (first,), event_id="SYNTHETIC-DUPLICATE", subject_id="SYNTHETIC-SUBJECT-B")
        replacement = event(
            3,
            (first, duplicate),
            operation="CORRECT",
            supersedes_event_id="SYNTHETIC-DUPLICATE",
            subject_id="SYNTHETIC-SUBJECT-A",
        )

        self.assertEqual(verify_chain((first, duplicate, replacement)).codes, ("DUPLICATE_EVENT_ID",))

    def test_nonmonotonic_timestamps_are_rejected(self):
        """Fails if time may move backwards between otherwise linked events."""
        first = event(2)
        second = event(1, (first,))

        self.assertIn("NON_MONOTONIC_TIMESTAMP", verify_chain((first, second)).codes)

    def test_malformed_timestamp_does_not_trigger_timestamp_order_code(self):
        """Fails if unvalidated timestamp text is compared as an ordered time."""
        first = event(1)
        malformed = replace(event(2, (first,)), recorded_at="0000-invalid")

        result = verify_chain((first, malformed))

        self.assertIn("INVALID_ENVELOPE", result.codes)
        self.assertNotIn("NON_MONOTONIC_TIMESTAMP", result.codes)

    def test_missing_supersession_target_is_rejected(self):
        """Fails if a correction may refer to an event absent from the ledger."""
        replacement = event(1, operation="CORRECT", supersedes_event_id="SYNTHETIC-MISSING")

        self.assertIn("SUPERSESSION_TARGET_NOT_FOUND", verify_chain((replacement,)).codes)

    def test_target_must_precede_the_replacement_event(self):
        """Fails if an event may target itself instead of an earlier event."""
        replacement = seal_envelope(
            event_id="SYNTHETIC-SELF",
            event_type="SYNTHETIC-TYPE-A",
            subject_id="SYNTHETIC-SUBJECT-A",
            operation="CORRECT",
            supersedes_event_id="SYNTHETIC-SELF",
            recorded_at=BASE_TIME + timedelta(seconds=1),
            payload={"SYNTHETIC": 1},
            metadata={"SYNTHETIC": "LEDGER"},
            previous_envelope_sha256=None,
        )

        self.assertIn("SUPERSESSION_TARGET_NOT_FOUND", verify_chain((replacement,)).codes)

    def test_cross_subject_and_cross_type_replacements_are_rejected(self):
        """Fails if replacement scope need not match the target event."""
        first = event(1)
        cross_subject = event(
            2, (first,), operation="CORRECT", supersedes_event_id=first.event_id, subject_id="SYNTHETIC-SUBJECT-B"
        )
        cross_type = event(
            3, (first,), operation="CORRECT", supersedes_event_id=first.event_id, event_type="SYNTHETIC-TYPE-B"
        )

        self.assertIn("SUPERSESSION_SCOPE_MISMATCH", verify_chain((first, cross_subject)).codes)
        self.assertIn("SUPERSESSION_SCOPE_MISMATCH", verify_chain((first, cross_type)).codes)

    def test_target_can_be_replaced_only_once(self):
        """Fails if two valid replacements may consume the same target."""
        first = event(1)
        correction = event(2, (first,), operation="CORRECT", supersedes_event_id=first.event_id)
        withdrawal = event(3, (first, correction), operation="WITHDRAW", supersedes_event_id=first.event_id)

        self.assertIn("SUPERSESSION_TARGET_ALREADY_REPLACED", verify_chain((first, correction, withdrawal)).codes)

    def test_failed_scope_attempt_does_not_consume_target(self):
        """Fails if an invalid replacement blocks a later valid replacement."""
        first = event(1)
        failed = event(
            2, (first,), operation="CORRECT", supersedes_event_id=first.event_id, subject_id="SYNTHETIC-SUBJECT-B"
        )
        valid = event(3, (first, failed), operation="CORRECT", supersedes_event_id=first.event_id)

        result = verify_chain((first, failed, valid))

        self.assertIn("SUPERSESSION_SCOPE_MISMATCH", result.codes)
        self.assertNotIn("SUPERSESSION_TARGET_ALREADY_REPLACED", result.codes)

    def test_invalid_envelope_and_invalid_event_are_collected_without_stopping(self):
        """Fails if independent envelope and lifecycle defects hide each other."""
        first = event(1)
        malformed = replace(
            event(2, (first,)),
            operation="SYNTHETIC-UNKNOWN",
            event_id="1-invalid",
        )

        result = verify_chain((first, malformed))

        self.assertIn("INVALID_ENVELOPE", result.codes)
        self.assertIn("INVALID_EVENT", result.codes)

    def test_malformed_objects_and_wrong_type_fields_fail_closed(self):
        """Fails if hostile runtime values can make verification raise or pass."""
        wrong_typed = replace(event(1), event_id=123)  # type: ignore[arg-type]

        result = verify_chain((object(), wrong_typed))  # type: ignore[arg-type]

        self.assertFalse(result.ok)
        self.assertIn("INVALID_ENVELOPE", result.codes)
        self.assertIn("INVALID_EVENT", result.codes)

    def test_unhashable_operation_fails_closed_without_raising(self):
        """Fails if an unhashable runtime operation reaches set membership."""
        malformed = replace(event(1), operation=[])  # type: ignore[arg-type]

        result = verify_chain((malformed,))

        self.assertFalse(result.ok)
        self.assertIn("INVALID_ENVELOPE", result.codes)
        self.assertIn("INVALID_EVENT", result.codes)

    def test_head_is_null_for_final_entry_without_a_valid_digest(self):
        """Fails if an unusable final digest is returned as a ledger head."""
        malformed_final = replace(event(1), envelope_sha256="SYNTHETIC-NOT-A-DIGEST")

        result = verify_chain((malformed_final,))

        self.assertIsNone(result.head_digest)

    def test_head_is_final_digest_when_only_other_validation_fails(self):
        """Fails if a self-consistent final digest is hidden by lifecycle errors."""
        invalid_final = invalid_lifecycle_event(1, ())

        result = verify_chain((invalid_final,))

        self.assertEqual(result.head_digest, invalid_final.envelope_sha256)
        self.assertIn("INVALID_EVENT", result.codes)

    def test_head_is_retained_for_envelope_invalid_final_with_well_formed_digest(self):
        """Fails if non-digest envelope defects hide a usable final head digest."""
        sealed = event(1)
        changed = replace(sealed, schema_version="SYNTHETIC-INVALID-SCHEMA")
        fields = changed.to_dict()
        fields.pop("envelope_sha256")
        malformed_final = replace(changed, envelope_sha256=sha256_hex(fields))

        result = verify_chain((malformed_final,))

        self.assertIn("INVALID_ENVELOPE", result.codes)
        self.assertEqual(result.head_digest, malformed_final.envelope_sha256)

    def test_append_returns_new_immutable_tuple_for_a_valid_event(self):
        """Fails if append mutates caller input or omits the requested event."""
        first = event(1)
        original = (first,)
        second = event(2, original)

        appended = append_event(original, second)

        self.assertEqual(original, (first,))
        self.assertEqual(appended, (first, second))
        self.assertIsNot(appended, original)

    def test_append_rejects_invalid_chain_with_sorted_code_only_error_text(self):
        """Fails if append accepts an invalid link or exposes unsafe error prose."""
        first = event(1)
        invalid = event(2)

        with self.assertRaises(ValueError) as raised:
            append_event((first,), invalid)

        self.assertEqual(str(raised.exception).split(", "), ["BROKEN_PREVIOUS_DIGEST"])
