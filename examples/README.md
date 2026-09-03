# SYNTHETIC lifecycle example

Every value in this directory is deliberately fabricated for documentation and
tests. `SYNTHETIC` is a fixture marker, all identifiers are opaque non-market
labels, the small integer values are invented, and the year 2099 timestamps are
future protocol fixtures. Nothing here came from an account, broker, holding,
trade, customer, third-party dataset, or real research record.

`SYNTHETIC_chain.jsonl` is a complete three-event lifecycle:

1. `SYNTHETIC-EVT-A` asserts the initial fixture.
2. `SYNTHETIC-EVT-B` corrects that assertion.
3. `SYNTHETIC-EVT-C` withdraws the correction.

Each event binds one correspondingly named payload plus the shared
`SYNTHETIC_metadata.json`. The ledger stores only digests, not those source
documents. From an installed local candidate, verify the chain with:

```text
decision-evidence verify-chain --ledger examples/SYNTHETIC_chain.jsonl
```

## Rebuild and verify the lifecycle

From the project root in Bash or Zsh, rebuild the same three events from the
synthetic payload and metadata files, then send the generated JSON Lines
directly to the verifier:

```bash
export PYTHONPATH=src
set -o pipefail
python3 examples/rebuild_synthetic_chain.py |
  python3 -m decision_evidence_ledger.cli verify-chain --ledger -
```

The verifier reports `"ok": true` and an event count of `3`. Run the Python
command without the pipe when you want to inspect the rebuilt envelopes.

The example demonstrates integrity and lifecycle mechanics only. It is not
market data, an investment result, or an expected-return claim.
