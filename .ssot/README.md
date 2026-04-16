# SSOT registry

This folder contains Tigrcorn's definitive machine-readable governance registry and source of truth.

The normalized `.ssot` scaffold is initialized from `ssot-registry init` through `tools/ssot_sync.py`.
Tigrcorn keeps the canonical registry here, but continues to use repo-native docs under `docs/` as the
canonical human narrative and release evidence chain.

Use these files first:

- definitive registry: `.ssot/registry.json`
- generator: `tools/ssot_sync.py`

What belongs here:

- the repo-local `ssot-registry` JSON document
- the normalized `.ssot` directories created from `ssot-registry init`
- any derived validation output written by the sync tool

What is intentionally not mirrored here:

- the package's template ADR/spec markdown set
- Tigrcorn's canonical human governance docs and release bundles, which remain under `docs/`

What does not change:

- the canonical human current-state chain remains under `docs/review/conformance/`
- the authoritative boundary remains `docs/review/conformance/CERTIFICATION_BOUNDARY.md`

Read next:

- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/gov/authoring.md`
