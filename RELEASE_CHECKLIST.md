# Release Checklist

This checklist is for a future maintainer. A checked item must be supported by
fresh evidence, not assumption.

## Current stop condition

- [ ] Explicit authorization to create or modify a remote repository has been
  received.
- [ ] Explicit authorization to push, upload, publish a package, create a tag,
  or create a hosted release has been received.

Until both permissions exist, do not push or upload anything. Local inspection,
tests, and documentation preparation do not grant publication permission.

## Ownership and identity

- [x] The copyright or licensing entity is confirmed in writing as `liver-detox`.
- [x] Each of the 41 source paths has a maintainer-provided origin statement
  and a local-candidate inclusion decision. This verified local-candidate
  statement does not grant publication authority.
- [x] The maintainer's intended public GitHub name is confirmed as `liver-detox`.
- [x] A GitHub-provided `noreply` address or another deliberately public commit
  address is selected; a private mailbox is not exposed accidentally.
- [ ] Commit authorship is reviewed before any history is published.
- [x] `CITATION.cff` content, including the public author name, is approved.

`CITATION.cff` uses only the approved alias and deliberately omits unapproved
repository and release identifiers.

## Scope, privacy, and data

- [ ] Only whitelist-approved files are present in the publication candidate.
- [ ] All examples and tests are synthetic and use opaque identifiers.
- [ ] No real account, position, order, trade, return, market data, provider
  export, screenshot, credential, private endpoint, personal detail, or private
  path is present.
- [ ] Hashes are reviewed as potentially identifying evidence, not treated as
  anonymization.
- [ ] Text and package-content scans are reviewed by a person.
- [ ] The project makes no investment, performance, security, adoption, or
  production-readiness promise unsupported by evidence.

## License and notices

- [ ] The Apache License 2.0 text is complete.
- [ ] The project metadata and source-distribution contents carry the intended
  license.
- [ ] Third-party code, data, fonts, media, and generated assets are absent or
  individually documented with compatible terms.
- [ ] `THIRD_PARTY_NOTICES.md` matches the actual distribution.
- [ ] A `NOTICE` file is added only if an included work creates that obligation
  or an approved attribution requires it.

## Technical verification

- [ ] With `PYTHONPYCACHEPREFIX` set outside the candidate tree,
  `python3 -m unittest discover -s tests -v` passes in a clean environment.
- [ ] `python3 -m compileall -q src tests scripts` exits successfully.
- [ ] Local installation in a disposable copy works without an undeclared
  runtime dependency.
- [x] The approved local CI configuration covers Python 3.11, 3.12, 3.13, and
  3.14 with a read-only token, no configured secrets, uploads, cache, or
  deployment steps. It remains inactive before the authorized first push.
- [ ] The first hosted CI run passes on the event commit; this cannot be claimed
  until the separately authorized push and exact archive check occur.
- [ ] After the first local commit and before the first push, the workflow's
  fixed Git archive step is run for that commit and provenance confirms 37
  ordinary project members.
- [ ] Python API and command-line examples are rerun exactly as documented.
- [ ] Failure examples return documented codes without revealing source input.
- [ ] The source distribution and wheel are built in a disposable directory.
- [ ] The complete file list of both package artifacts is inspected.
- [ ] The source distribution follows `MANIFEST.in` and excludes local guides,
  progress records, task reports, caches, credentials, and unrelated files.

## Local history preparation

- [ ] A new repository is initialized only in the clean public-candidate
  directory, never in or over the private source repository.
- [ ] After separate authorization, files are staged only from the exact,
  verified provenance-derived path list rather than `git add .`.
- [ ] `git status --short` and `git diff --cached --name-only` show only approved
  files.
- [ ] A local commit is created only after the public commit name and address
  are confirmed.
- [ ] The local commit contains no inherited private history.

`git init` creates local version-control metadata. `git commit` records a local
snapshot. Neither command uploads files. `git push` sends commits to a remote
server and remains forbidden until separately authorized.

## Remote and public release

- [ ] The repository owner, name, visibility, description, and default branch
  are approved.
- [ ] A private vulnerability-reporting route is enabled and tested, then
  documented in `SECURITY.md` without exposing a private mailbox.
- [ ] The exact remote URL is copied from the approved GitHub repository; no
  guessed destination is used.
- [ ] The first push is independently reviewed immediately before execution.
- [ ] Branch protection and workflow review ownership (for example CODEOWNERS)
  are approved and configured.
- [ ] The development version is replaced with an approved release version in
  both package metadata and the importable package.
- [ ] A release tag, hosted release, and package-index upload receive separate
  authorization.
- [ ] Public claims about users, downloads, adoption, maintenance, or ecosystem
  value are made only from verifiable public evidence.
