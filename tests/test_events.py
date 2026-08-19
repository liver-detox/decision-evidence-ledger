"""Contract tests for generic evidence-event lifecycles."""

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from decision_evidence_ledger.events import (
    OPERATIONS,
    create_event,
    validate_event,
)


RECORDED_AT = datetime(2026, 1, 2, 3, 4, 5, 6007, tzinfo=timezone.utc)


def create(**changes):
    """Create one valid generic event with digestable fixtures."""
    fields = {
        "event_id": "event-01",
        "event_type": "observation",
        "subject_id": "subject-01",
        "operation": "ASSERT",
        "supersedes_event_id": None,
        "recorded_at": RECORDED_AT,
        "payload": {"finding": "observed"},
        "metadata": {"source": "test"},
        "previous_envelope_sha256": None,
    }
    fields.update(changes)
    return create_event(**fields)


class EventLifecycleTests(unittest.TestCase):
    """Ensure event lifecycles are validated without retaining evidence."""

    def test_operations_list_all_supported_lifecycle_actions(self):
        """Fails if callers cannot discover every supported lifecycle action."""
        self.assertEqual(OPERATIONS, ("ASSERT", "CORRECT", "WITHDRAW"))

    def test_valid_assert_has_no_superseded_event(self):
        """Fails if a valid initial assertion cannot be created and validated."""
        event = create()

        self.assertTrue(validate_event(event).ok)

    def test_valid_correct_has_a_superseded_event(self):
        """Fails if a valid correction cannot be created and validated."""
        event = create(operation="CORRECT", supersedes_event_id="event-00")

        self.assertTrue(validate_event(event).ok)

    def test_valid_withdraw_has_a_superseded_event(self):
        """Fails if a valid withdrawal cannot be created and validated."""
        event = create(operation="WITHDRAW", supersedes_event_id="event-00")

        self.assertTrue(validate_event(event).ok)

    def test_assert_with_target_is_rejected(self):
        """Fails if an assertion can incorrectly replace another event."""
        with self.assertRaisesRegex(ValueError, "^invalid supersession$"):
            create(supersedes_event_id="event-00")

    def test_correct_or_withdraw_without_target_is_rejected(self):
        """Fails if replacement actions can omit their intended target."""
        for operation in ("CORRECT", "WITHDRAW"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "^invalid supersession$"):
                    create(operation=operation)

    def test_self_supersession_is_rejected(self):
        """Fails if an event can claim to replace itself."""
        with self.assertRaisesRegex(ValueError, "^invalid supersession$"):
            create(operation="CORRECT", supersedes_event_id="event-01")

    def test_unknown_operation_is_rejected(self):
        """Fails if unsupported lifecycle actions reach envelope sealing."""
        with self.assertRaisesRegex(ValueError, "^unknown operation$"):
            create(operation="REPLACE")

    def test_sealed_event_retains_digest_only_privacy(self):
        """Fails if creation exposes source payload or metadata on the event."""
        payload = {"private": ["detail"]}
        metadata = {"origin": "private"}
        event = create(payload=payload, metadata=metadata)

        self.assertNotIn("payload", event.__dataclass_fields__)
        self.assertNotIn("metadata", event.__dataclass_fields__)
        self.assertNotIn("payload", event.to_dict())
        self.assertNotIn("metadata", event.to_dict())

    def test_validate_reports_exact_sorted_lifecycle_codes_without_raising(self):
        """Fails if malformed runtime lifecycle values raise or hide defects."""
        valid = create()
        malformed_cases = (
            (replace(valid, operation="REPLACE"), ("UNKNOWN_OPERATION",)),
            (replace(valid, supersedes_event_id="event-00"), ("INVALID_SUPERSESSION",)),
            (replace(valid, operation="CORRECT"), ("INVALID_SUPERSESSION",)),
            (replace(valid, operation="WITHDRAW"), ("INVALID_SUPERSESSION",)),
            (
                replace(valid, operation="REPLACE", supersedes_event_id="event-01"),
                ("INVALID_SUPERSESSION", "UNKNOWN_OPERATION"),
            ),
            (replace(valid, operation=None), ("UNKNOWN_OPERATION",)),
        )

        for event, expected_codes in malformed_cases:
            with self.subTest(event=event):
                result = validate_event(event)
                self.assertFalse(result.ok)
                self.assertEqual(result.codes, expected_codes)

    def test_creation_leaves_payload_and_metadata_unchanged(self):
        """Fails if creation mutates caller-owned source evidence."""
        payload = {"e\u0301": [{"z": 1, "a": 2}]}
        metadata = {"outer": ["cafe\u0301"]}
        payload_before = {"e\u0301": [{"z": 1, "a": 2}]}
        metadata_before = {"outer": ["cafe\u0301"]}

        create(payload=payload, metadata=metadata)

        self.assertEqual(payload, payload_before)
        self.assertEqual(metadata, metadata_before)
