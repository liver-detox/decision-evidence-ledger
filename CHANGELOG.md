# Changelog

This file records user-visible project changes.

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
