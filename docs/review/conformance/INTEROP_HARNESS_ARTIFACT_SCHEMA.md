# Interop harness artifact schema

This document records the promoted artifact schema introduced by the Phase 9B harness-foundation checkpoint.

## Scope

This schema applies to **newly generated** independent-certification bundles produced by the shared interop harness.

It does **not** retroactively redefine the older canonical 0.3.6 preserved bundles, which remain authoritative for the current package-wide certification boundary.

## Required bundle files

Every newly generated Phase 9B-style independent bundle must contain:

- `manifest.json`
- `summary.json`
- `index.json`

### `manifest.json`

Must record at least:

- bundle kind
- matrix name
- commit hash
- artifact schema version
- required bundle files
- required scenario files
- environment snapshot
- matrix hash

### `summary.json`

Must record at least:

- bundle kind
- matrix name
- commit hash
- total / passed / failed / skipped counts
- scenario ids

### `index.json`

Must record at least:

- bundle kind
- matrix name
- commit hash
- scenario entries
- per-scenario summary / index / result paths

## Required per-scenario files

Every scenario directory must contain:

- `summary.json`
- `index.json`
- `result.json`
- `scenario.json`
- `command.json`
- `env.json`
- `versions.json`
- `wire_capture.json`

### `result.json`

The pass/fail record for the scenario, including observed transcripts, negotiation, and artifact metadata.

### `scenario.json`

The materialized scenario definition and capture contract used for the run.

### `command.json`

The materialized command lines, adapters, and working directories used for the SUT and peer.

### `env.json`

The scenario-specific environment snapshot, including the shared interop context and the materialized `INTEROP_*` variables used by each side.

### `versions.json`

Version / provenance metadata for the SUT and peer.

### `wire_capture.json`

Wire/log capture inventory, including packet traces, qlogs when applicable, stdout/stderr logs, transcript files, and negotiation records.

### `summary.json` and `index.json`

The per-scenario summary and artifact inventory used by the validator.

## Validator behavior

`src/tigrcorn/compat/release_gates.py` now exposes helpers that reject a bundle when:

- required bundle files are absent
- required per-scenario files are absent
- the per-scenario inventory is missing or incomplete
- summary / index / result pass flags disagree
- command, environment, version, or wire-capture records are absent

## Current proof bundle

The first Phase 9B proof bundle using this schema is:

- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-harness-foundation-bundle/`

That proof bundle is intentionally small. It demonstrates schema completeness and validator enforcement without claiming that the full strict-target independent scenario backlog is already closed.
