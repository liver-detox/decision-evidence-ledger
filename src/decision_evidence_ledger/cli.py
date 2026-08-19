"""A payload-safe command-line interface for local evidence envelopes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Sequence
import unicodedata

from .canonical import canonicalize
from .envelopes import EvidenceEnvelope, verify_envelope
from .events import create_event
from .ledger import verify_chain


_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


class _ArgumentFailure(Exception):
    """Raised instead of allowing argparse to print an unsafe diagnostic."""


class _SafeParser(argparse.ArgumentParser):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        raise _ArgumentFailure


class _SingleSource(argparse.Action):
    """Accept each file/stdin source option exactly once."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str,
        option_string: str | None = None,
    ) -> None:
        if getattr(namespace, self.dest, None) is not None:
            parser.error("")
        setattr(namespace, self.dest, values)


def _emit(value: dict[str, object]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _failure(code: str) -> int:
    _emit({"codes": [code], "ok": False})
    return 2


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys, including canonically equivalent spellings."""
    result: dict[str, object] = {}
    normalized_keys: set[str] = set()
    for key, value in pairs:
        normalized = unicodedata.normalize("NFC", key)
        if normalized in normalized_keys:
            raise ValueError
        normalized_keys.add(normalized)
        result[key] = value
    return result


def _invalid_constant(value: str) -> object:
    """Reject JSON extensions such as NaN before they become Python floats."""
    raise ValueError


def _load_json(source: str) -> object:
    try:
        if source == "-":
            contents = sys.stdin.read()
        else:
            contents = Path(source).read_text(encoding="utf-8")
        return canonicalize(
            json.loads(contents, object_pairs_hook=_json_object, parse_constant=_invalid_constant)
        )
    except Exception:
        raise ValueError from None


def _load_jsonl(source: str) -> list[object]:
    try:
        if source == "-":
            contents = sys.stdin.read()
        else:
            contents = Path(source).read_text(encoding="utf-8")
        lines = contents.splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError
        return [
            canonicalize(json.loads(line, object_pairs_hook=_json_object, parse_constant=_invalid_constant))
            for line in lines
        ]
    except Exception:
        raise ValueError from None


def _timestamp(value: str) -> datetime:
    if _TIMESTAMP.fullmatch(value) is None:
        raise ValueError
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError from None


def _envelope(value: object) -> EvidenceEnvelope:
    try:
        return EvidenceEnvelope.from_dict(value)  # type: ignore[arg-type]
    except Exception:
        raise ValueError from None


def _parser() -> _SafeParser:
    parser = _SafeParser(prog="decision-evidence")
    commands = parser.add_subparsers(dest="command", required=True)

    seal = commands.add_parser("seal")
    for option in ("event-id", "event-type", "subject-id", "operation", "recorded-at", "payload"):
        seal.add_argument(f"--{option}", required=True, action=_SingleSource if option == "payload" else None)
    seal.add_argument("--metadata", action=_SingleSource)
    seal.add_argument("--supersedes-event-id")
    seal.add_argument("--previous-envelope-sha256")

    verify = commands.add_parser("verify-envelope")
    verify.add_argument("--envelope", required=True, action=_SingleSource)
    verify.add_argument("--payload", action=_SingleSource)
    verify.add_argument("--metadata", action=_SingleSource)

    chain = commands.add_parser("verify-chain")
    chain.add_argument("--ledger", required=True, action=_SingleSource)
    return parser


def _ambiguous_stdin(args: argparse.Namespace) -> bool:
    if args.command == "seal":
        sources = (args.payload, args.metadata)
    elif args.command == "verify-envelope":
        sources = (args.envelope, args.payload, args.metadata)
    else:
        sources = (args.ledger,)
    return sum(source == "-" for source in sources) > 1


def _seal(args: argparse.Namespace) -> int:
    try:
        payload = _load_json(args.payload)
        metadata = {} if args.metadata is None else _load_json(args.metadata)
    except ValueError:
        return _failure("INVALID_INPUT")
    try:
        envelope = create_event(
            event_id=args.event_id,
            event_type=args.event_type,
            subject_id=args.subject_id,
            operation=args.operation,
            supersedes_event_id=args.supersedes_event_id,
            recorded_at=_timestamp(args.recorded_at),
            payload=payload,
            metadata=metadata,
            previous_envelope_sha256=args.previous_envelope_sha256,
        )
    except Exception:
        return _failure("INVALID_ARGUMENTS")
    _emit({"envelope": envelope.to_dict(), "ok": True})
    return 0


def _verify_envelope(args: argparse.Namespace) -> int:
    try:
        envelope = _envelope(_load_json(args.envelope))
        payload = _load_json(args.payload) if args.payload is not None else None
        metadata = _load_json(args.metadata) if args.metadata is not None else None
    except ValueError:
        return _failure("INVALID_INPUT")
    try:
        kwargs: dict[str, object] = {}
        if args.payload is not None:
            kwargs["payload"] = payload
        if args.metadata is not None:
            kwargs["metadata"] = metadata
        result = verify_envelope(envelope, **kwargs)
    except Exception:
        return _failure("INVALID_INPUT")
    _emit({"codes": list(result.codes), "ok": result.ok})
    return 0 if result.ok else 2


def _verify_chain(args: argparse.Namespace) -> int:
    try:
        entries = tuple(_envelope(value) for value in _load_jsonl(args.ledger))
    except ValueError:
        return _failure("INVALID_INPUT")
    try:
        result = verify_chain(entries)
    except Exception:
        return _failure("INVALID_INPUT")
    _emit(
        {
            "codes": list(result.codes),
            "event_count": result.event_count,
            "head_digest": result.head_digest,
            "ok": result.ok,
        }
    )
    return 0 if result.ok else 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run one local command without exposing input contents or exceptions."""
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except _ArgumentFailure:
        return _failure("INVALID_ARGUMENTS")
    except SystemExit as error:
        return 0 if error.code == 0 else _failure("INVALID_ARGUMENTS")
    if _ambiguous_stdin(args):
        return _failure("INVALID_ARGUMENTS")
    if args.command == "seal":
        return _seal(args)
    if args.command == "verify-envelope":
        return _verify_envelope(args)
    if args.command == "verify-chain":
        return _verify_chain(args)
    return _failure("INVALID_ARGUMENTS")


if __name__ == "__main__":
    raise SystemExit(main())
