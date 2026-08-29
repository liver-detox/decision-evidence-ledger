"""Black-box contracts for the payload-safe command-line interface."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest


PYTHON = sys.executable
ENV = {**os.environ, "PYTHONPATH": "src"}
BASE = (
    "--event-id", "SYNTHETIC-EVENT-01",
    "--event-type", "SYNTHETIC-TYPE",
    "--subject-id", "SYNTHETIC-SUBJECT",
    "--operation", "ASSERT",
    "--recorded-at", "2026-01-02T03:04:05.006007Z",
)


class CliTests(unittest.TestCase):
    """Keep all subprocess-facing output compact, JSON-only, and safe."""

    def test_subprocesses_use_the_active_python_runtime(self):
        """Fails if subprocess tests depend on one developer's interpreter path."""
        self.assertEqual(PYTHON, sys.executable)

    def test_public_cli_test_source_contains_no_local_user_path(self):
        """Fails if a developer-specific absolute path enters the public tests."""
        local_user_root = "/" + "Users" + "/"

        self.assertNotIn(local_user_root, Path(__file__).read_text(encoding="utf-8"))

    def run_cli(self, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, "-m", "decision_evidence_ledger.cli", *args],
            cwd=Path(__file__).parents[1],
            env=ENV,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def response(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertTrue(result.stdout.endswith("\n"))
        return json.loads(result.stdout)

    def seal(
        self, payload_path: str, *extra: str, input_text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
            "seal", *BASE, "--payload", payload_path, *extra, input_text=input_text
        )

    def test_seal_file_is_one_safe_json_line(self):
        """Fails if sealing prints any source payload or non-JSON output."""
        with tempfile.TemporaryDirectory() as directory:
            payload_path = Path(directory, "payload.json")
            payload_path.write_text('{"SYNTHETIC":"SYNTHETIC-DISTINCTIVE-PAYLOAD-01"}', encoding="utf-8")
            result = self.seal(str(payload_path))

        value = self.response(result)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(set(value), {"envelope", "ok"})
        self.assertTrue(value["ok"])
        self.assertNotIn("SYNTHETIC-DISTINCTIVE-PAYLOAD-01", result.stdout)
        self.assertNotIn('"payload"', result.stdout)
        self.assertNotIn('"metadata"', result.stdout)

    def test_seal_accepts_stdin_and_default_metadata_is_deterministic(self):
        """Fails if stdin or the implicit empty metadata binding is unstable."""
        first = self.seal("-", input_text='{"SYNTHETIC":"VALUE"}')
        second = self.seal("-", input_text='{"SYNTHETIC":"VALUE"}')

        first_value = self.response(first)
        second_value = self.response(second)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first_value["envelope"], second_value["envelope"])

    def test_verify_envelope_checks_correct_wrong_omitted_and_null_payload(self):
        """Fails if verification cannot distinguish omitted evidence from JSON null."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload.json"
            wrong = root / "wrong.json"
            null = root / "null.json"
            payload.write_text('{"SYNTHETIC":"VALUE"}', encoding="utf-8")
            wrong.write_text('{"SYNTHETIC":"OTHER"}', encoding="utf-8")
            null.write_text("null", encoding="utf-8")
            sealed = self.seal(str(payload))
            envelope = root / "envelope.json"
            envelope.write_text(json.dumps(self.response(sealed)["envelope"]), encoding="utf-8")

            omitted = self.run_cli("verify-envelope", "--envelope", str(envelope))
            correct = self.run_cli("verify-envelope", "--envelope", str(envelope), "--payload", str(payload))
            wrong_result = self.run_cli("verify-envelope", "--envelope", str(envelope), "--payload", str(wrong))
            null_result = self.run_cli("verify-envelope", "--envelope", str(envelope), "--payload", str(null))

        for result in (omitted, correct):
            self.assertEqual(result.returncode, 0)
            self.assertEqual(self.response(result), {"codes": [], "ok": True})
        self.assertEqual(wrong_result.returncode, 2)
        self.assertEqual(self.response(wrong_result), {"codes": ["PAYLOAD_DIGEST_MISMATCH"], "ok": False})
        self.assertEqual(null_result.returncode, 2)
        self.assertEqual(self.response(null_result), {"codes": ["PAYLOAD_DIGEST_MISMATCH"], "ok": False})

    def test_verify_envelope_accepts_explicit_json_null(self):
        """Fails if a null JSON payload is treated as missing input."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            null = root / "null.json"
            null.write_text("null", encoding="utf-8")
            sealed = self.seal(str(null))
            envelope = root / "envelope.json"
            envelope.write_text(json.dumps(self.response(sealed)["envelope"]), encoding="utf-8")
            result = self.run_cli("verify-envelope", "--envelope", str(envelope), "--payload", str(null))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.response(result), {"codes": [], "ok": True})

    def test_verify_chain_reports_safe_metadata_for_valid_and_broken_jsonl(self):
        """Fails if chain verification omits structural metadata or masks a broken link."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_payload = root / "first.json"
            second_payload = root / "second.json"
            first_payload.write_text('{"SYNTHETIC":1}', encoding="utf-8")
            second_payload.write_text('{"SYNTHETIC":2}', encoding="utf-8")
            first = self.response(self.seal(str(first_payload)))["envelope"]
            first_digest = first["envelope_sha256"]  # type: ignore[index]
            second = self.response(self.run_cli(
                "seal", "--event-id", "SYNTHETIC-EVENT-02", "--event-type", "SYNTHETIC-TYPE",
                "--subject-id", "SYNTHETIC-SUBJECT", "--operation", "ASSERT",
                "--recorded-at", "2026-01-02T03:04:06.006007Z", "--payload", str(second_payload),
                "--previous-envelope-sha256", first_digest,
            ))["envelope"]
            valid = root / "valid.jsonl"
            valid.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")
            broken = root / "broken.jsonl"
            broken.write_text(json.dumps(second) + "\n", encoding="utf-8")
            valid_result = self.run_cli("verify-chain", "--ledger", str(valid))
            broken_result = self.run_cli("verify-chain", "--ledger", str(broken))

        valid_value = self.response(valid_result)
        self.assertEqual(valid_result.returncode, 0)
        self.assertEqual(valid_value["codes"], [])
        self.assertEqual(valid_value["event_count"], 2)
        self.assertRegex(valid_value["head_digest"], r"^[0-9a-f]{64}$")
        self.assertEqual(broken_result.returncode, 2)
        self.assertEqual(self.response(broken_result)["codes"], ["BROKEN_PREVIOUS_DIGEST"])

    def test_malformed_duplicate_unicode_duplicate_and_wrong_shape_are_invalid_input(self):
        """Fails if hostile JSON is parsed permissively or reaches verifiers."""
        cases = (
            '{"SYNTHETIC":',
            '{"SYNTHETIC":1,"SYNTHETIC":2}',
            '{"e\\u0301":1,"é":2}',
            '{"SYNTHETIC":"WRONG-SHAPE"}',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, contents in enumerate(cases):
                path = root / f"SYNTHETIC-{index}.json"
                path.write_text(contents, encoding="utf-8")
                result = self.run_cli("verify-envelope", "--envelope", str(path))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.response(result), {"codes": ["INVALID_INPUT"], "ok": False})

    def test_malformed_jsonl_is_invalid_input(self):
        """Fails if malformed ledger records leak parser details or partial verification."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "SYNTHETIC-malformed.jsonl")
            path.write_text('{"SYNTHETIC":1}\n{', encoding="utf-8")
            result = self.run_cli("verify-chain", "--ledger", str(path))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.response(result), {"codes": ["INVALID_INPUT"], "ok": False})

    def test_missing_file_and_private_looking_path_remain_secret(self):
        """Fails if CLI errors disclose filenames, paths, or exception prose."""
        marker = "SYNTHETIC-PRIVATE-PATH-MARKER-9a5d"
        result = self.run_cli("verify-envelope", "--envelope", f"/missing/{marker}.json")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.response(result), {"codes": ["INVALID_INPUT"], "ok": False})
        self.assertNotIn(marker, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_invalid_arguments_and_unknown_command_are_safe(self):
        """Fails if argparse diagnostics or invalid commands escape the safe schema."""
        for arguments in (("seal",), ("SYNTHETIC-UNKNOWN",)):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.response(result), {"codes": ["INVALID_ARGUMENTS"], "ok": False})
                self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_help_exits_zero(self):
        """Fails if standard help cannot be requested without a command error."""
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("seal", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_package_declares_the_fixed_console_entry_point(self):
        """Fails if installing the package omits the promised CLI executable."""
        project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(
            project["project"].get("scripts"),
            {"decision-evidence": "decision_evidence_ledger.cli:main"},
        )

    def test_help_uses_the_fixed_console_name(self):
        """Fails if help advertises an undeclared executable name."""
        result = self.run_cli("seal", "--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("usage: decision-evidence seal", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_subcommand_help_explains_lifecycle_and_json_inputs(self):
        """Fails if first-time CLI users must infer the documented input model."""
        seal = self.run_cli("seal", "--help")
        verify = self.run_cli("verify-envelope", "--help")
        chain = self.run_cli("verify-chain", "--help")

        for result in (seal, verify, chain):
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
        self.assertIn("ASSERT, CORRECT, or WITHDRAW", seal.stdout)
        self.assertIn("YYYY-MM-DDTHH:MM:SS.ffffffZ", seal.stdout)
        self.assertIn("JSON payload file", seal.stdout)
        self.assertIn("Envelope JSON file", verify.stdout)
        self.assertIn("JSON Lines ledger", chain.stdout)

    def test_abbreviated_long_options_are_invalid_arguments(self):
        """Fails if argparse accepts undeclared long-option abbreviations."""
        result = self.run_cli(
            "seal", "--event-i", "SYNTHETIC-EVENT-01", "--event-t", "SYNTHETIC-TYPE",
            "--subject", "SYNTHETIC-SUBJECT", "--oper", "ASSERT",
            "--recorded", "2026-01-02T03:04:05.006007Z", "--pay", "-",
            input_text='{"SYNTHETIC":"VALUE"}',
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.response(result), {"codes": ["INVALID_ARGUMENTS"], "ok": False})

    def test_repeated_source_option_and_multiple_stdin_sources_are_invalid_arguments(self):
        """Fails if a source may be repeated or stdin may be consumed ambiguously."""
        repeated = self.run_cli(
            "seal", *BASE, "--payload", "-", "--payload", "-", input_text='{"SYNTHETIC":1}'
        )
        ambiguous = self.run_cli(
            "seal", *BASE, "--payload", "-", "--metadata", "-", input_text='{"SYNTHETIC":1}'
        )
        verify_repeated = self.run_cli(
            "verify-envelope", "--envelope", "-", "--payload", "-", "--payload", "-",
            input_text='{"SYNTHETIC":1}',
        )
        verify_ambiguous = self.run_cli(
            "verify-envelope", "--envelope", "-", "--metadata", "-", input_text='{"SYNTHETIC":1}'
        )

        for result in (repeated, ambiguous, verify_repeated, verify_ambiguous):
            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.response(result), {"codes": ["INVALID_ARGUMENTS"], "ok": False})

    def test_metadata_sources_null_binding_and_privacy(self):
        """Fails if metadata sources are unverified, confused with null, or disclosed."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload.json"
            metadata = root / "metadata.json"
            wrong_metadata = root / "wrong-metadata.json"
            null = root / "null.json"
            payload.write_text('{"SYNTHETIC":"PAYLOAD"}', encoding="utf-8")
            metadata.write_text('{"SYNTHETIC":"SYNTHETIC-DISTINCTIVE-METADATA-01"}', encoding="utf-8")
            wrong_metadata.write_text('{"SYNTHETIC":"OTHER"}', encoding="utf-8")
            null.write_text("null", encoding="utf-8")
            sealed = self.seal(str(payload), "--metadata", str(metadata))
            envelope = root / "envelope.json"
            envelope.write_text(json.dumps(self.response(sealed)["envelope"]), encoding="utf-8")
            correct = self.run_cli("verify-envelope", "--envelope", str(envelope), "--metadata", str(metadata))
            wrong = self.run_cli("verify-envelope", "--envelope", str(envelope), "--metadata", str(wrong_metadata))
            null_result = self.run_cli("verify-envelope", "--envelope", str(envelope), "--metadata", str(null))
            stdin_sealed = self.seal(str(payload), "--metadata", "-", input_text="null")
            null_sealed = self.seal(str(payload), "--metadata", str(null))
            null_envelope = root / "null-envelope.json"
            null_envelope.write_text(json.dumps(self.response(null_sealed)["envelope"]), encoding="utf-8")
            null_correct = self.run_cli(
                "verify-envelope", "--envelope", str(null_envelope), "--metadata", str(null)
            )

        self.assertEqual(correct.returncode, 0)
        self.assertEqual(self.response(correct), {"codes": [], "ok": True})
        for result in (wrong, null_result):
            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.response(result), {"codes": ["METADATA_DIGEST_MISMATCH"], "ok": False})
        self.assertEqual(stdin_sealed.returncode, 0)
        self.assertEqual(null_correct.returncode, 0)
        self.assertEqual(self.response(null_correct), {"codes": [], "ok": True})
        self.assertNotIn("SYNTHETIC-DISTINCTIVE-METADATA-01", sealed.stdout)
        self.assertNotIn('"metadata"', sealed.stdout)

    def test_nonstandard_and_float_json_are_invalid_input_for_all_sources(self):
        """Fails if unsupported JSON numbers reach core APIs or become mismatch codes."""
        values = ("NaN", "Infinity", "-Infinity", "1.5")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid_payload = root / "payload.json"
            valid_payload.write_text('{"SYNTHETIC":1}', encoding="utf-8")
            for index, contents in enumerate(values):
                source = root / f"SYNTHETIC-number-{index}.json"
                source.write_text(contents, encoding="utf-8")
                seal_result = self.seal(str(source))
                metadata_result = self.seal(str(valid_payload), "--metadata", str(source))
                self.assertEqual(self.response(seal_result), {"codes": ["INVALID_INPUT"], "ok": False})
                self.assertEqual(self.response(metadata_result), {"codes": ["INVALID_INPUT"], "ok": False})
                self.assertEqual(seal_result.returncode, 2)
                self.assertEqual(metadata_result.returncode, 2)
                invalid_ledger = root / f"SYNTHETIC-invalid-ledger-{index}.jsonl"
                invalid_ledger.write_text(contents + "\n", encoding="utf-8")
                ledger_result = self.run_cli("verify-chain", "--ledger", str(invalid_ledger))
                self.assertEqual(self.response(ledger_result), {"codes": ["INVALID_INPUT"], "ok": False})

            envelope = root / "envelope.json"
            envelope.write_text(json.dumps(self.response(self.seal(str(valid_payload)))["envelope"]), encoding="utf-8")
            invalid_payload = root / "SYNTHETIC-invalid-payload.json"
            invalid_payload.write_text("NaN", encoding="utf-8")
            verify_result = self.run_cli("verify-envelope", "--envelope", str(envelope), "--payload", str(invalid_payload))

        self.assertEqual(self.response(verify_result), {"codes": ["INVALID_INPUT"], "ok": False})

    def test_nested_duplicate_and_nfc_keys_are_invalid_for_every_input_kind(self):
        """Fails if nested hostile keys are accepted for payload, metadata, or JSONL."""
        cases = ('{"SYNTHETIC":{"KEY":1,"KEY":2}}', '{"SYNTHETIC":{"e\\u0301":1,"é":2}}')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid_payload = root / "valid.json"
            valid_payload.write_text('{"SYNTHETIC":1}', encoding="utf-8")
            for index, contents in enumerate(cases):
                source = root / f"SYNTHETIC-nested-{index}.json"
                source.write_text(contents, encoding="utf-8")
                for result in (
                    self.seal(str(source)),
                    self.seal(str(valid_payload), "--metadata", str(source)),
                ):
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(self.response(result), {"codes": ["INVALID_INPUT"], "ok": False})
                ledger = root / f"SYNTHETIC-ledger-{index}.jsonl"
                ledger.write_text(contents + "\n", encoding="utf-8")
                result = self.run_cli("verify-chain", "--ledger", str(ledger))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.response(result), {"codes": ["INVALID_INPUT"], "ok": False})

    def test_blank_jsonl_and_private_argument_values_are_safe(self):
        """Fails if blank records or invalid argument values disclose sensitive text."""
        marker = "SYNTHETIC-PRIVATE-MARKER-1c8b"
        with tempfile.TemporaryDirectory() as directory:
            blank = Path(directory, "SYNTHETIC-blank.jsonl")
            blank.write_text('{"SYNTHETIC":1}\n\n', encoding="utf-8")
            blank_result = self.run_cli("verify-chain", "--ledger", str(blank))
        invalid_values = (
            ("--event-id", f"1{marker}"),
            ("--recorded-at", marker),
            ("--previous-envelope-sha256", marker),
        )

        self.assertEqual(self.response(blank_result), {"codes": ["INVALID_INPUT"], "ok": False})
        for option, value in invalid_values:
            with self.subTest(option=option):
                arguments = list(BASE)
                if option in arguments:
                    arguments[arguments.index(option) + 1] = value
                else:
                    arguments.extend((option, value))
                result = self.run_cli("seal", *arguments, "--payload", "-", input_text='{"SYNTHETIC":1}')
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.response(result), {"codes": ["INVALID_ARGUMENTS"], "ok": False})
                self.assertNotIn(marker, result.stdout + result.stderr)

    def test_multiple_verifier_integrity_codes_are_preserved(self):
        """Fails if validly parsed tampering is collapsed into an input error."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "payload.json"
            payload.write_text('{"SYNTHETIC":1}', encoding="utf-8")
            envelope = self.response(self.seal(str(payload)))["envelope"]
            envelope["schema_version"] = "SYNTHETIC-BAD"
            envelope["event_id"] = "1SYNTHETIC-BAD"
            envelope["envelope_sha256"] = "SYNTHETIC-BAD"
            path = root / "envelope.json"
            path.write_text(json.dumps(envelope), encoding="utf-8")
            result = self.run_cli("verify-envelope", "--envelope", str(path))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            self.response(result),
            {
                "codes": [
                    "ENVELOPE_DIGEST_MISMATCH", "INVALID_DIGEST_FORMAT", "INVALID_IDENTIFIER",
                    "INVALID_SCHEMA_VERSION",
                ],
                "ok": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
