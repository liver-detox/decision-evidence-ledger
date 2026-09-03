# Decision Evidence Ledger

Decision Evidence Ledger helps local workflow maintainers keep corrections and
withdrawals reviewable without copying source payloads into the ledger.

In an optional three-tool workflow, Decision Evidence Ledger is the recording
step: which exact artifact supports the decision, and can later corrections or
withdrawals be reviewed?

**On the first run:** verify the included three-event synthetic chain and get a
clear `ok`, event count, and head digest.

## Quickstart

From the project root, with Python 3.11 or later:

```sh
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

## Use it locally

The project requires Python 3.11 or later and a local copy. It has no
third-party runtime dependency; its local build configuration uses
`setuptools`, and the development-tool inventory is not yet final.

Inspect the CLI or run the tests directly from the checkout:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m decision_evidence_ledger.cli --help
```

The installed CLI provides `seal`, `verify-envelope`, and `verify-chain`. The
Python API exposes `create_event`, `verify_envelope`, `verify_chain`, and
`append_event`. Verification returns stable diagnostic codes; the CLI exits
`0` on success or help and `2` on rejected input or failed verification. For
the synthetic lifecycle walkthrough, see [the examples](examples/README.md);
run each command with `--help` to inspect its inputs. Maintainers preparing an
installation or release candidate should use [the local release guide](docs/LOCAL_RELEASE_GUIDE.md).

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

## Maintainer release gates

Maintainers only: **ordinary library and CLI users do not need to run these
gates.** `scripts/verify_distribution.py`, `scripts/verify_provenance.py`, and
the release checklist are maintainer release gates, not user prerequisites.

The current version is `v0.1.0`, available as a GitHub source release. There
is no package-index release and no verified evidence of users, downloads,
external adoption, or production use.

Release docs: [local guide](docs/LOCAL_RELEASE_GUIDE.md),
[checklist](RELEASE_CHECKLIST.md), and [security policy](SECURITY.md).

## License

Copyright 2026 liver-detox.

This project is licensed under the Apache License 2.0; see
[LICENSE](LICENSE). Third-party status is recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
