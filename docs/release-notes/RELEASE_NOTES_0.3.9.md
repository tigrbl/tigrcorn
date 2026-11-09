# Release notes — tigrcorn 0.3.9

`tigrcorn` `0.3.9` promotes the previously validated 0.3.9 release root to the canonical authoritative release.

## What changed in this promotion

- promoted `docs/review/conformance/releases/0.3.9/release-0.3.9/` to the canonical release root
- updated `pyproject.toml` from `0.3.6` to `0.3.9`
- aligned the authoritative release-boundary metadata, external matrices, release manifests, summaries, and current-state snapshots with the promoted 0.3.9 release
- preserved the Step 8 strict-validation bundle and its passing results

## Current certification status

- authoritative boundary: `True`
- strict target boundary: `True`
- composite promotion target: `True`

The promoted 0.3.9 release is **certifiably fully RFC compliant**, **strict-target certifiably fully RFC compliant**, and **certifiably fully featured**.

## Notable preserved bundles

- independent certification matrix
- same-stack replay matrix
- mixed compatibility matrix
- flag-surface certification bundle
- operator-surface certification bundle
- performance certification bundle
- certification-environment freeze bundle
- aioquic adapter preflight bundle
- strict-validation bundle

## Operational note

The local workspace used for this checkpoint still runs under Python 3.13. The frozen release-workflow contract remains Python 3.11 or 3.12 with `.[certification,dev]` installed. That does not change the preserved release-artifact truth of the canonical 0.3.9 release root.
