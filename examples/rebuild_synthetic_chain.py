#!/usr/bin/env python3
"""Rebuild the documented synthetic lifecycle and write JSON Lines to stdout."""

from datetime import datetime, timezone
import json
from pathlib import Path

from decision_evidence_ledger import append_event, create_event


EXAMPLES = Path(__file__).parent


def _read_json(filename: str) -> object:
    return json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))


def main() -> None:
    metadata = _read_json("SYNTHETIC_metadata.json")
    events = ()
    specifications = (
        ("SYNTHETIC-EVT-A", "ASSERT", None, 1, "SYNTHETIC_assert_payload.json"),
        (
            "SYNTHETIC-EVT-B",
            "CORRECT",
            "SYNTHETIC-EVT-A",
            2,
            "SYNTHETIC_correct_payload.json",
        ),
        (
            "SYNTHETIC-EVT-C",
            "WITHDRAW",
            "SYNTHETIC-EVT-B",
            3,
            "SYNTHETIC_withdraw_payload.json",
        ),
    )

    for event_id, operation, supersedes, sequence, payload_file in specifications:
        event = create_event(
            event_id=event_id,
            event_type="SYNTHETIC-TYPE",
            subject_id="SYNTHETIC-SUBJECT-ALPHA",
            operation=operation,
            supersedes_event_id=supersedes,
            recorded_at=datetime(
                2099,
                1,
                1,
                0,
                0,
                sequence,
                sequence,
                tzinfo=timezone.utc,
            ),
            payload=_read_json(payload_file),
            metadata=metadata,
            previous_envelope_sha256=(
                events[-1].envelope_sha256 if events else None
            ),
        )
        events = append_event(events, event)

    for event in events:
        print(
            json.dumps(
                event.to_dict(),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
