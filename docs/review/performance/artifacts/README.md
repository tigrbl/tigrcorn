# Performance artifacts

This directory preserves the upgraded strict-performance evidence roots.

## Roots

- `phase6_reference_baseline/` — the preserved accepted baseline lane for this checkpoint
- `phase6_current_release/` — the preserved current release lane evaluated against that baseline

The directory names remain historical, but the artifact contract is now the stricter **Phase 9G** contract.

Each profile directory now contains:

- `result.json`
- `summary.json`
- `env.json`
- `percentile_histogram.json`
- `raw_samples.csv`
- `command.json`
- `correctness.json`

Root-level `summary.json` and `index.json` files summarize the run.
