# Decision Evidence Ledger

Decision Evidence Ledger helps local workflow maintainers keep corrections and
withdrawals reviewable without copying source payloads into the ledger.

**On the first run:** verify the included three-event synthetic chain and get a
clear `ok`, event count, and head digest.

## Quickstart

From the project root, with Python 3.11 or later:

```sh
PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/decision-evidence-ledger-pycache" \
PYTHONPATH=src python3 -m decision_evidence_ledger.cli \
  verify-chain --ledger examples/SYNTHETIC_chain.jsonl
```

The result is one JSON line with `"ok": true`, `"event_count": 3`, and a
`head_digest`. The example covers `ASSERT`, `CORRECT`, and `WITHDRAW`; its
ledger contains digests, not the source payloads. See [the synthetic example](examples/README.md).

## How the record stays reviewable

A decision or observation often changes over time. Keeping only the latest
value hides whether an earlier assertion was corrected or withdrawn. This
project provides a narrow, generic record format with three lifecycle events:

| Operation | Meaning | Supersession rule |
| --- | --- | --- |
| `ASSERT` | Introduce an initial assertion. | Must not name an earlier event. |
| `CORRECT` | Add a correction while retaining history. | Must name one earlier event with the same subject and type. |
| `WITHDRAW` | Mark an earlier event as withdrawn without deleting it. | Must name one earlier event with the same subject and type. |

Each corrected or withdrawn event may be replaced only once. A later
correction may correct an earlier correction by naming that correction as its
target.

The ledger can detect structural inconsistencies such as a changed envelope,
a missing link, a duplicate event identifier, time moving backwards, or an
invalid supersession relationship. It checks consistency, not truth.

## Trust, privacy, and input boundaries

- A valid digest proves only that supplied bytes canonicalize to the same
  digest; it does not prove that an underlying statement is true. A chain is
  meaningful only if its head digest, or another reference, is retained
  independently; replacing both is outside this project's detection boundary.
- The project does not authenticate people, sign timestamps, manage access,
  store secrets, encrypt evidence, or provide secure deletion. A hash is not
  anonymization or encryption, and identifiers and timestamps remain visible.
  Use opaque, non-sensitive identifiers.
- Payload and metadata remain with the caller; this project does not move,
  redact, or delete them. Do not put sensitive data or credentials in examples,
  issue reports, identifiers, file names, or command arguments—shell history
  and process inspection can expose arguments and paths.
- The CLI accepts JSON `null`, booleans, integers, strings, lists, and
  string-keyed objects; it rejects floats and duplicate normalized keys. It has
  no market-data, brokerage, account, trading, or runtime-network capability,
  and provides no investment advice, return forecast, or performance promise.

Read [SECURITY.md](SECURITY.md) before reporting a concern. No private
reporting channel is available; never place sensitive details in a public
report.

## Use it locally

The project requires Python 3.11 or later and a local copy. It has no
third-party runtime dependency; its local build configuration uses
`setuptools`, and the development-tool inventory is not yet final.

Inspect the CLI or run the tests directly from the checkout:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m decision_evidence_ledger.cli --help
```

The installed CLI provides `seal`, `verify-envelope`, and `verify-chain`.
The Python API exposes `create_event`, `verify_envelope`, `verify_chain`, and
`append_event`. Verification returns stable diagnostic codes; the CLI exits
`0` on success/help and `2` on rejected input or failed verification.

Package tooling can add generated files, so build or install only from a
disposable copy:

```sh
install_root="$(mktemp -d "${TMPDIR:-/tmp}/decision-evidence-ledger-install.XXXXXX")"
cp -R . "$install_root/project"
python3 -m venv "$install_root/venv"
"$install_root/venv/bin/python" -m pip install --no-deps --no-build-isolation \
  "$install_root/project"
```

See [the local release guide](docs/LOCAL_RELEASE_GUIDE.md) before preparing a
release candidate.

## Project status, provenance, and participation

The current version is `v0.1.0`, available as a GitHub source release. There
is no package-index release or verified adoption. CI runs on pushes and pull
requests across Python 3.11–3.14; it is a project self-test, not a containment
boundary.

`PROVENANCE.json` records the maintainer's inclusion decisions for the public
source release. It is not independent proof of ownership and does not
authorize a package-index upload. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for participation and release
gates.

## License

Copyright 2026 liver-detox.

This project is licensed under the Apache License 2.0; see
[LICENSE](LICENSE). Third-party status is recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
