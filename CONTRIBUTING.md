# Contributing

## Current state

This project is still a local development candidate. There is no public remote
repository and no active pull-request intake. A pull request is a proposed
change submitted through a hosted Git repository; that workflow belongs to a
future, explicitly authorized publication stage.

These rules define the minimum bar for any future contribution.

## Evidence and privacy rules

Every example, fixture, bug reproduction, and documentation sample must be
synthetic. Use opaque identifiers that do not encode a person, company,
security, account, portfolio, or real decision.

Do not submit:

- real accounts, positions, orders, transactions, returns, or brokerage data;
- market data, provider exports, screenshots, receipts, or derived datasets;
- credentials, tokens, private endpoints, personal email addresses, or private
  file paths;
- confidential prompts, internal reports, or files copied from another
  project;
- third-party code without a recorded source and a compatible license.

Hashing sensitive material does not make it safe to publish. Do not add the
material or its digest when its presence, format, or guessability could reveal
private information.

`PROVENANCE.json` is a maintainer statement of origin and local-candidate
inclusion for each listed path. It is not independent proof of rights and does
not authorize publication; that authorization remains `NOT_GRANTED`.

## Future hosted checks

The local candidate includes a reviewed CI workflow, but it remains inactive
until an authorized first push. It runs only on a GitHub-hosted runner with a
read-only repository token and no configured project secrets, uploads, cache,
deployment, or notification steps. Pull-request code can execute with network
access on that runner and can modify the proposed workflow or tests, so CI is
not a containment boundary. Branch protection, workflow review ownership, and
the first hosted run remain separate future gates.

## Local development

The runtime package has zero third-party dependencies. The tests use Python's
standard `unittest` framework.

Before running local Python commands, set one cache location outside the
candidate directory:

```sh
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/decision-evidence-ledger-pycache"
```

`.gitignore` does not make these generated files acceptable to the strict
provenance verifier.

From the project root, run:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests scripts
```

`unittest` executes the tests. `compileall` asks Python to compile each module,
which catches syntax errors but does not replace the tests.

When reviewing a change:

1. Keep the public API generic and digest-only.
2. Add or update a synthetic test for changed behavior.
3. Preserve fail-closed behavior: ambiguity or malformed input must not be
   silently accepted.
4. Preserve compact diagnostic codes and avoid echoing source input in errors.
5. Run the full test and compile commands above.
6. Recheck the release checklist for privacy, license, and package-content
   boundaries.

## Change scope

The initial public scope excludes market adapters, data-provider clients,
brokerage connections, authentication, investment analytics, and real-data
examples. Proposals in those areas should not be submitted as ordinary feature
changes.

## License and authorship

Contributors must have the right to submit their work and must disclose any
third-party source or license obligation. Contributions intentionally submitted
for inclusion are handled under the project [LICENSE](LICENSE), unless they are
conspicuously marked otherwise and separately accepted by the maintainer. No
separate contributor agreement is currently configured.

The public maintainer identity is `liver-detox`. Contribution intake is not yet
open. Before it opens, the maintainer must document the review process, private
security channel, and public contributor identity policy while preserving the
privacy requirements above.
