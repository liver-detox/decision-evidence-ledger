"""Contract tests for deterministic canonical JSON utilities."""

from datetime import datetime, timedelta, timezone
import hashlib
import unittest

from decision_evidence_ledger.canonical import (
    canonical_json_bytes,
    canonical_timestamp,
    canonicalize,
    sha256_hex,
)


class CanonicalJsonTests(unittest.TestCase):
    """Ensure canonical encodings are stable and reject non-JSON values."""

    def test_mapping_order_and_unicode_normalization_produce_identical_bytes(self):
        """Fails if mappings or NFC-equivalent strings yield different encodings."""
        composed = {"z": "caf\u00e9", "\u00e9": ["\u00e9"]}
        decomposed = {"e\u0301": ["e\u0301"], "z": "cafe\u0301"}

        self.assertEqual(canonical_json_bytes(composed), canonical_json_bytes(decomposed))

    def test_canonical_json_bytes_match_the_exact_compact_utf8_encoding(self):
        """Fails if encoding uses escaping, spacing, or an unstable key order."""
        value = {"b": None, "a": [True, "\u00e9"]}

        self.assertEqual(canonical_json_bytes(value), b'{"a":[true,"\xc3\xa9"],"b":null}')

    def test_sha256_hex_hashes_the_expected_canonical_bytes(self):
        """Fails if hashing uses anything other than the canonical byte sequence."""
        expected = b'{"a":[true,"\xc3\xa9"],"b":null}'

        self.assertEqual(
            sha256_hex({"b": None, "a": [True, "\u00e9"]}),
            hashlib.sha256(expected).hexdigest(),
        )

    def test_duplicate_normalized_keys_are_rejected(self):
        """Fails if NFC key collisions silently overwrite evidence."""
        with self.assertRaisesRegex(ValueError, "^duplicate normalized key$"):
            canonicalize({"\u00e9": 1, "e\u0301": 2})

    def test_rejects_every_non_json_payload_category(self):
        """Fails if unsupported values are accepted into canonical evidence payloads."""
        unsupported_values = {
            "float": 1.5,
            "nan": float("nan"),
            "infinity": float("inf"),
            "bytes": b"value",
            "tuple": ("value",),
            "set": {"value"},
            "datetime": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "non_string_dict_key": {1: "value"},
            "other_object": object(),
        }

        for category, value in unsupported_values.items():
            with self.subTest(category=category):
                with self.assertRaises((TypeError, ValueError)):
                    canonicalize(value)

    def test_rejects_nested_invalid_values(self):
        """Fails if validation does not traverse lists and mappings recursively."""
        for value in ([{"bad": b"value"}], {"outer": ("bad",)}):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    canonicalize(value)

    def test_equivalent_aware_timestamps_use_the_same_utc_string(self):
        """Fails if aware timestamps do not normalize to precise UTC output."""
        utc_value = datetime(2026, 1, 2, 11, 4, 5, tzinfo=timezone.utc)
        offset_value = datetime(
            2026, 1, 2, 19, 4, 5, tzinfo=timezone(timedelta(hours=8))
        )

        self.assertEqual(canonical_timestamp(utc_value), "2026-01-02T11:04:05.000000Z")
        self.assertEqual(canonical_timestamp(offset_value), "2026-01-02T11:04:05.000000Z")

    def test_naive_timestamp_is_rejected(self):
        """Fails if a timestamp without a UTC offset is accepted."""
        with self.assertRaises((TypeError, ValueError)):
            canonical_timestamp(datetime(2026, 1, 2, 11, 4, 5))
