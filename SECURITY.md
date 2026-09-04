# Security Policy

## Current support status

Version `0.2.0` is the current GitHub source-release version. No package-index
publication, private security-support channel, response time, or remediation
deadline is promised.

The project does not currently offer a private reporting route. A public GitHub
Issue may be used only for a nonsensitive report that contains no secret,
private evidence, identifying data, or exploit detail. This file intentionally
contains no invented email address or URL.

## What to report privately

Examples of relevant security concerns include:

- a way to make modified evidence pass an integrity check;
- canonicalization differences that create ambiguous digests;
- parser behavior that exposes input content, filenames, or exception details;
- chain verification that misses deletion, reordering, duplication, or invalid
  supersession;
- packaging that unintentionally includes secrets, private paths, local task
  records, or source evidence;
- denial-of-service behavior from a small, validly formed input.

Investment outcomes, market-data correctness, provider availability, and
brokerage behavior are outside the project because it has no such integration.

## Protect the report itself

Never paste a secret, credential, private key, personal record, account detail,
real trade, private path, or confidential evidence into a public GitHub Issue,
Discussion, pull request, log, or screenshot. Because no private route is
currently published, retain any sensitive report locally rather than adding it
to this project.

A useful private report can describe:

- the affected version and command or API;
- a minimal synthetic reproduction;
- expected and observed diagnostic codes;
- potential impact;
- whether the issue is already public.

Use opaque identifiers and synthetic JSON. Do not attach real evidence.

## Security boundary

Decision Evidence Ledger checks deterministic JSON bindings and ledger
structure. It does not establish factual truth, identity, trusted time,
authorization, confidentiality, non-repudiation, secure storage, or secure
deletion. SHA-256 digests are not anonymization. A separately trusted head
digest is needed to make full-chain replacement detectable.

The project is supplied without warranty under the terms in [LICENSE](LICENSE).
