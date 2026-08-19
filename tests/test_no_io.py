"""Proof that the public core stays in memory and has no I/O side effects."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import importlib
import unittest
from unittest import mock

import pathlib
import socket
import subprocess
import urllib.request


CORE_MODULES = (
    "decision_evidence_ledger.canonical",
    "decision_evidence_ledger.envelopes",
    "decision_evidence_ledger.events",
    "decision_evidence_ledger.ledger",
)


class NoIoTests(unittest.TestCase):
    """Fail whenever an ordinary core workflow reaches an I/O boundary."""

    def io_guard(self) -> ExitStack:
        stack = ExitStack()
        for target in (
            "builtins.open",
            "os.open",
            "pathlib.Path.open",
            "pathlib.Path.read_bytes",
            "pathlib.Path.read_text",
            "pathlib.Path.write_bytes",
            "pathlib.Path.write_text",
            "socket.socket",
            "socket.create_connection",
            "subprocess.Popen",
            "subprocess.run",
            "urllib.request.urlopen",
        ):
            stack.enter_context(mock.patch(target, side_effect=AssertionError(f"I/O attempted: {target}")))
        return stack

    def test_core_modules_import_without_application_io(self):
        """Import-time module code must not call files, processes, or networks."""
        with self.io_guard():
            for module_name in CORE_MODULES:
                importlib.reload(importlib.import_module(module_name))

    def test_complete_core_workflow_uses_memory_only(self):
        """Canonicalize, seal, validate, append, and verify entirely in memory."""
        from decision_evidence_ledger.canonical import (
            canonical_json_bytes,
            canonical_timestamp,
            canonicalize,
            sha256_hex,
        )
        from decision_evidence_ledger.envelopes import seal_envelope, verify_envelope
        from decision_evidence_ledger.events import create_event, validate_event
        from decision_evidence_ledger.ledger import append_event, verify_chain

        first_time = datetime(2099, 1, 1, tzinfo=timezone(timedelta(hours=8)))
        second_time = first_time + timedelta(seconds=1)
        payload = {"SYNTHETIC": True, "value": 1, "label": "e\u0301"}
        metadata = {"SYNTHETIC": True, "source_kind": "fabricated-example"}

        with self.io_guard():
            self.assertEqual(canonicalize(payload)["label"], "é")
            self.assertIsInstance(canonical_json_bytes(payload), bytes)
            self.assertEqual(len(sha256_hex(payload)), 64)
            self.assertTrue(canonical_timestamp(first_time).endswith("Z"))

            sealed = seal_envelope(
                event_id="SYNTHETIC-EVT-A",
                event_type="SYNTHETIC-TYPE",
                subject_id="SYNTHETIC-SUBJECT-ALPHA",
                operation="ASSERT",
                supersedes_event_id=None,
                recorded_at=first_time,
                payload=payload,
                metadata=metadata,
                previous_envelope_sha256=None,
            )
            self.assertTrue(verify_envelope(sealed, payload=payload, metadata=metadata).ok)

            correction = create_event(
                event_id="SYNTHETIC-EVT-B",
                event_type="SYNTHETIC-TYPE",
                subject_id="SYNTHETIC-SUBJECT-ALPHA",
                operation="CORRECT",
                supersedes_event_id=sealed.event_id,
                recorded_at=second_time,
                payload={"SYNTHETIC": True, "value": 2},
                metadata=metadata,
                previous_envelope_sha256=sealed.envelope_sha256,
            )
            self.assertTrue(validate_event(correction).ok)
            chain = append_event((sealed,), correction)
            result = verify_chain(chain)

        self.assertTrue(result.ok)
        self.assertEqual(result.event_count, 2)
        self.assertEqual(result.head_digest, correction.envelope_sha256)


if __name__ == "__main__":
    unittest.main()
