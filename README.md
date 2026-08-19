# Decision Evidence Ledger

Decision Evidence Ledger is a small, local Python library for creating and
checking **digest-only evidence envelopes**. An envelope records identifiers,
a UTC timestamp, SHA-256 digests, and an optional link to the preceding
envelope. It does not retain the source payload or metadata inside the
envelope.

The current version is `0.1.0.dev0`. It is a local development candidate: it
has not been published, and there is no verified evidence of users, downloads,
external adoption, or production use.

## What problem does it address?

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

## Important limits

- A valid digest proves only that the supplied bytes canonicalize to the same
  digest. It does not prove that the underlying statement is true.
- A hash is not anonymization or encryption. Short, predictable, or otherwise
  guessable values may be recovered by trying possible inputs.
- A chain is meaningful only when a trusted copy of its head digest or another
  reference is retained independently. Replacing a whole chain and its only
  reference is outside this project's detection boundary.
- The project does not authenticate people, sign timestamps, manage access,
  store secrets, encrypt evidence, or provide secure deletion.
- Identifiers and timestamps remain visible in an envelope. Use opaque,
  non-sensitive identifiers.
- Source payload and metadata remain wherever the caller stored them. This
  project does not move, redact, or delete those files.
- The command line accepts JSON values made from `null`, booleans, integers,
  strings, lists, and string-keyed objects. Floating-point values and duplicate
  normalized keys are rejected.
- This project has no market-data adapter, brokerage connection, account
  access, trading function, or runtime network dependency.
- Nothing in this project is investment advice, a return forecast, or a
  promise of financial performance.

## Requirements

- Python 3.11 or later, subject to verification on every version claimed by a
  future release.
- No third-party runtime dependency.
- A local copy of this project.

The package uses only the Python standard library at runtime. Its local build
configuration uses `setuptools`; the development-tool inventory is not yet
final.

## Local provenance record

`PROVENANCE.json` is a maintainer-provided statement of each local candidate
path's origin and local-candidate inclusion decision. It is not independent
proof of rights, ownership, or provenance, and it does not grant publication
authorization. Publication authorization remains `NOT_GRANTED`.

Run `python3 scripts/verify_provenance.py .` only on a clean candidate tree:
the verifier accepts no cache, build, environment, or other extra files.
`.gitignore` does not relax this strict check.

Before running local Python commands, set one cache location outside the
candidate directory:

```sh
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/decision-evidence-ledger-pycache"
```

## Run locally without installing

From the project root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m decision_evidence_ledger.cli --help
```

The first command runs the standard-library test suite. The second starts the
command-line interface directly from `src`.

## Optional local installation

Build and install only from a disposable copy: package tooling may create
generated files, which do not belong in the strict candidate tree.

```sh
install_root="$(mktemp -d "${TMPDIR:-/tmp}/decision-evidence-ledger-install.XXXXXX")"
cp -R . "$install_root/project"
cd "$install_root/project"
python3 -m venv "$install_root/venv"
source "$install_root/venv/bin/activate"
python -m pip install --no-deps --no-build-isolation .
decision-evidence --help
```

`--no-deps` means no runtime package is requested. `--no-build-isolation`
means the command uses build tooling already present in the environment. If a
compatible build tool is missing, stop and review the local release guide
before allowing any download.

## Python API example

This example uses only synthetic content and opaque identifiers:

```python
from datetime import datetime, timezone

from decision_evidence_ledger import create_event, verify_envelope, verify_chain

payload = {"scenario": "SYNTHETIC", "choice": "OPTION-A"}
metadata = {"source": "SYNTHETIC-GENERATOR"}

event = create_event(
    event_id="SYNTHETIC-EVENT-A",
    event_type="SYNTHETIC-DECISION",
    subject_id="OPAQUE-SUBJECT-A",
    operation="ASSERT",
    supersedes_event_id=None,
    recorded_at=datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    payload=payload,
    metadata=metadata,
    previous_envelope_sha256=None,
)

assert verify_envelope(event, payload=payload, metadata=metadata).ok
assert verify_chain((event,)).ok

print(event.to_dict())  # identifiers, timestamp, and digests only
```

`create_event` validates lifecycle rules and returns an immutable
`EvidenceEnvelope`. `verify_envelope` checks the envelope and, when supplied,
recomputes payload or metadata bindings. `verify_chain` checks an ordered
sequence. `append_event` returns a new tuple only when the resulting chain is
valid.

## Command-line example

After local installation, create a file named `synthetic-payload.json`:

```json
{"scenario":"SYNTHETIC","choice":"OPTION-A"}
```

Seal it with opaque identifiers:

```sh
decision-evidence seal \
  --event-id SYNTHETIC-EVENT-A \
  --event-type SYNTHETIC-DECISION \
  --subject-id OPAQUE-SUBJECT-A \
  --operation ASSERT \
  --recorded-at 2030-01-02T03:04:05.000001Z \
  --payload synthetic-payload.json
```

The command prints one compact JSON line containing an `envelope` object. The
source payload itself is not printed. To verify the binding later, save only
that nested envelope object as `synthetic-envelope.json`, then run:

```sh
decision-evidence verify-envelope \
  --envelope synthetic-envelope.json \
  --payload synthetic-payload.json
```

A ledger file is JSON Lines: one complete envelope object per non-blank line,
in order. Verify it with:

```sh
decision-evidence verify-chain --ledger synthetic-ledger.jsonl
```

Use `--previous-envelope-sha256` when sealing every event after the first. Use
`--supersedes-event-id` with `CORRECT` or `WITHDRAW`. One input may be `-` to
read JSON from standard input; a single command cannot read two inputs from
standard input because their boundaries would be ambiguous.

## Error model

Python creation functions raise `ValueError` for invalid construction input.
Verification functions return immutable result objects with:

- `ok`: `True` only when no diagnostic code was found;
- `codes`: stable, sorted diagnostic strings;
- for a chain, `event_count` and the final usable `head_digest`.

Envelope diagnostics include invalid schema, identifier, timestamp, digest
format, and digest mismatches. Lifecycle diagnostics include unknown operation
and invalid supersession. Chain diagnostics include broken links, duplicate
identifiers, non-monotonic timestamps, unreadable ledger input, missing or
mismatched supersession targets, and repeated replacement of one target.

The command line returns exit status `0` for success or help, and `2` for a
rejected input or failed verification. It prints a single JSON line and uses
generic `INVALID_ARGUMENTS` or `INVALID_INPUT` codes for parsing failures so
that exception text and input content are not echoed. Successful envelope
output still exposes the identifiers and timestamp that the caller supplied.

## Security and privacy

Do not place secrets, personal data, account information, real positions,
transactions, market data, private file paths, or provider credentials in
examples, issue reports, identifiers, filenames, or command arguments. Shell
history and operating-system process inspection can expose command arguments
and paths even when this program's JSON output does not.

Read [SECURITY.md](SECURITY.md) before reporting a security concern. A private
reporting channel is a publication gate and has not yet been configured.

## Project status and participation

This directory is local only. There is no remote repository, public release,
package-index release, contribution intake, or security-reporting endpoint.
The project is maintained under the public identity `liver-detox`; no public
contact data is provided in this local candidate.

The reviewed CI workflow is implemented locally in `.github/workflows/ci.yml`,
but remains inactive until a separately authorized first push. It tests the
event commit on Python 3.11 through 3.14 with a read-only repository token,
no configured project secrets, uploads, cache, or deployment steps. Hosted
pull-request code can still execute with network access and can change the
workflow; the workflow is a project self-test rather than a containment
boundary. The 41-path provenance statement records a maintainer decision to
include this local candidate only and does not grant publication authority.
Future participation rules are described in [CONTRIBUTING.md](CONTRIBUTING.md),
and the publication gates are in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).

## License

Copyright 2026 liver-detox.

This local development candidate is licensed under the Apache License 2.0; see
[LICENSE](LICENSE). Third-party status is recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
