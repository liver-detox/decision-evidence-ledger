# Changelog

This file records user-visible project changes. The source repository is
public, but every entry below remains development work rather than a formal
release history.

## Unreleased

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
- Authorization limited to publishing the reviewed source repository on public
  GitHub; tags, hosted releases, and package-index uploads remain separate.
- A least-privilege CI workflow for Python 3.11 through 3.14.

## 0.1.0.dev0 — local development snapshot

### Present in the candidate

- Standard-library canonical JSON and SHA-256 binding functions.
- Immutable digest-only evidence envelopes.
- `ASSERT`, `CORRECT`, and `WITHDRAW` lifecycle validation.
- Ordered ledger verification and append validation.
- Local `decision-evidence` command-line interface.
- Standard-library unit tests.

This version has not been published as a tagged GitHub release or package-index
release and is not presented as production-ready.
