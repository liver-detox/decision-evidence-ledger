"""Deterministic normalization and encoding for JSON evidence payloads."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import TypeAlias
import unicodedata


JsonValue: TypeAlias = None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]


def canonicalize(value: object) -> JsonValue:
    """Return a recursively validated JSON value normalized to Unicode NFC."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("dictionary keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ValueError("duplicate normalized key")
            normalized[normalized_key] = canonicalize(item)
        return {key: normalized[key] for key in sorted(normalized)}
    raise TypeError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Encode a validated payload into compact, sorted UTF-8 JSON bytes."""
    return json.dumps(
        canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_hex(value: object) -> str:
    """Return the lowercase SHA-256 digest of canonical JSON bytes."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_timestamp(value: datetime) -> str:
    """Format an aware timestamp as a fixed-precision UTC timestamp."""
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime")
    if value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    utc_value = value.astimezone(timezone.utc)
    return (
        f"{utc_value.year:04d}-{utc_value.month:02d}-{utc_value.day:02d}"
        f"T{utc_value.hour:02d}:{utc_value.minute:02d}:{utc_value.second:02d}"
        f".{utc_value.microsecond:06d}Z"
    )
