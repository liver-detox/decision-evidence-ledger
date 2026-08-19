# Release Checklist

This checklist is for a future maintainer. A checked item must be supported by
fresh evidence, not assumption.

## Current authorization boundary

- [x] Explicit authorization to create the public GitHub source repository and
  push the reviewed source history has been received.
- [ ] Separate authorization to create a version tag, hosted release, or
  package-index upload has been received.

Only the first public GitHub source publication is authorized. Do not create a
version tag, hosted release, or package-index upload under this authorization.

## Ownership and identity

- [x] The copyright or licensing entity is confirmed in writing as `liver-detox`.
- [x] Each of the 41 source paths has a maintainer-provided origin statement
  and an inclusion decision. This statement is not independent rights proof.
- [x] The maintainer's intended public GitHub name is confirmed as `liver-detox`.
- [x] A GitHub-provided `noreply` address or another deliberately public commit
  address is selected; a private mailbox is not exposed accidentally.
- [x] Commit authorship is reviewed before any history is published.
- [x] `CITATION.cff` content, including the public author name, is approved.

`CITATION.cff` uses only the approved alias and deliberately omits unapproved
repository and release identifiers.

## Scope, privacy, and data

- [x] Only whitelist-approved files are present in the publication candidate.
- [x] All examples and tests are synthetic and use opaque identifiers.
- [x] No real account, position, order, trade, return, market data, provider
  export, screenshot, credential, private endpoint, personal detail, or private
  path is present.
- [x] Hashes are reviewed as potentially identifying evidence, not treated as
  anonymization.
- [x] Text and package-content scans are reviewed by a person.
- [x] The project makes no investment, performance, security, adoption, or
  production-readiness promise unsupported by evidence.

## License and notices

- [x] The Apache License 2.0 text is complete.
- [x] The project metadata and source-distribution contents carry the intended
  license.
- [x] Third-party code, data, fonts, media, and generated assets are absent or
  individually documented with compatible terms.
- [x] `THIRD_PARTY_NOTICES.md` matches the actual distribution.
- [x] A `NOTICE` file is added only if an included work creates that obligation
  or an approved attribution requires it.

## Technical verification

- [x] With `PYTHONPYCACHEPREFIX` set outside the candidate tree,
  `python3 -m unittest discover -s tests -v` passes in a clean environment.
- [x] `python3 -m compileall -q src tests scripts` exits successfully.
- [x] Local installation in a disposable copy works without an undeclared
  runtime dependency.
- [x] The approved local CI configuration covers Python 3.11, 3.12, 3.13, and
  3.14 with a read-only token, no configured secrets, uploads, cache, or
  deployment steps.
- [ ] The first hosted CI run passes on the event commit; this cannot be claimed
  until the separately authorized push and exact archive check occur.
- [x] After the first local commit and before the first push, the workflow's
  fixed Git archive step is run for that commit and provenance confirms 37
  ordinary project members.
- [x] Python API and command-line examples are rerun exactly as documented.
- [x] Failure examples return documented codes without revealing source input.
- [x] The source distribution and wheel are built in a disposable directory.
- [x] The complete file list of both package artifacts is inspected.
- [x] The source distribution follows `MANIFEST.in` and excludes local guides,
  progress records, task reports, caches, credentials, and unrelated files.

## Local history preparation

- [x] A new repository is initialized only in the clean public-candidate
  directory, never in or over the private source repository.
- [x] After separate authorization, files are staged only from the exact,
  verified provenance-derived path list rather than `git add .`.
- [x] `git status --short` and `git diff --cached --name-only` show only approved
  files.
- [x] A local commit is created only after the public commit name and address
  are confirmed.
- [x] The local commit contains no inherited private history.

`git init` creates local version-control metadata. `git commit` records a local
snapshot. Neither command uploads files. `git push` sends commits to a remote
server and requires the source-publication authorization recorded above.

## Remote and public release

- [x] The repository owner, name, visibility, description, and default branch
  are approved.
- [ ] A private vulnerability-reporting route is enabled and tested, then
  documented in `SECURITY.md` without exposing a private mailbox.
- [ ] The exact remote URL is copied from the approved GitHub repository; no
  guessed destination is used.
- [x] The first push is independently reviewed immediately before execution.
- [ ] Branch protection and workflow review ownership (for example CODEOWNERS)
  are approved and configured.
- [ ] The development version is replaced with an approved release version in
  both package metadata and the importable package.
- [ ] A release tag, hosted release, and package-index upload receive separate
  authorization.
- [x] Public claims about users, downloads, adoption, maintenance, or ecosystem
  value are made only from verifiable public evidence.
