# Changelog

This file records user-visible project changes.

## 0.2.1 — clearer safe recovery from local command failures

### What users can do now

- Receive a short, actionable JSON `message` alongside the existing failure
  code when a required command option is missing, a named JSON input cannot be
  read or parsed, the ledger input is not valid JSON Lines, or `--recorded-at`
  has the wrong format.
- Keep using the same success JSON, diagnostic codes, and exit statuses in
  scripts; messages use only fixed command names, option names, and input
  categories, never supplied values, paths, payloads, or exception text.

The runtime schema and verification rules are unchanged from `0.2.0`.

## 0.2.0 — clearer first run and reproducible lifecycle

### What users can do now

- Verify the included three-event lifecycle from a source checkout and receive
  one result containing `ok`, the event count, and the current head digest.
- Rebuild the same `ASSERT` → `CORRECT` → `WITHDRAW` lifecycle from the included
  synthetic inputs, then send it directly to the verifier.
- Discover the JSON inputs for `seal`, `verify-envelope`, and `verify-chain`
  through clearer command-line help.

### Improved

- The README now leads with the first useful result and keeps maintainer-only
  release checks out of the user's path.
- The reproducible lifecycle example is included in the source archive and is
  checked against the documented chain by an automated test.

The runtime API, evidence schema, dependency policy, and Apache-2.0 license are
unchanged from `0.1.0`.

## 0.1.0 — first GitHub source release preparation

### Added

- Local documentation for the digest-only evidence model, lifecycle semantics,
  Python API, command-line interface, privacy boundary, and error model.
- Local contribution, conduct, security, release-checklist, and release-guide
  documents.
- A strict source-distribution manifest policy.
- Alias-only public author and citation metadata, with synchronized release
  guidance.
- A 41-path local provenance ledger, exact source-only policy, and strict
  reduced source-archive completeness verifier. The ledger is a maintainer
  statement and inclusion record, not independent rights proof.
- Authorization to create the `v0.1.0` tag and hosted GitHub source release;
  this excludes package-index uploads.
- A least-privilege CI workflow for Python 3.11 through 3.14.

### Present in the candidate

- Standard-library canonical JSON and SHA-256 binding functions.
- Immutable digest-only evidence envelopes.
- `ASSERT`, `CORRECT`, and `WITHDRAW` lifecycle validation.
- Ordered ledger verification and append validation.
- Local `decision-evidence` command-line interface.
- Standard-library unit tests.

This release is prepared for the authorized `v0.1.0` tag and hosted GitHub
source release. Local preparation does not itself create either remote object,
and no package-index release is authorized. It is not presented as
production-ready and has no evidence of users, downloads, external adoption,
or production use.
