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

The example demonstrates integrity and lifecycle mechanics only. It is not
market data, an investment result, or an expected-return claim.
