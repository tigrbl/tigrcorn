# Phase 9B independent-harness foundation

This checkpoint executes **Phase 9B** of `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`.

It builds the reusable harness and artifact schema needed for the remaining third-party strict-target scenarios. It is **not** a claim that the repository is already strict-target complete or certifiably fully featured under the stricter promotion profile.

## What changed in this checkpoint

### 1. Standardized third-party wrapper families now exist

A reusable wrapper registry now exists in `tools/interop_wrappers.py` and is published in machine-readable form at `docs/review/conformance/interop_wrapper_registry.current.json`.

The standardized wrapper families now cover the exact peer ecosystems named in Phase 9B:

- `curl`
- `websockets`
- `h2`
- `aioquic`
- `openssl`

The canonical independent matrix in `docs/review/conformance/external_matrix.release.json` now also carries Phase 9B wrapper metadata:

- artifact schema version
- required bundle files
- required scenario files
- wrapper-family registry reference
- per-scenario wrapper identifiers for the already-green independent scenarios

### 2. The interop runner now emits a promoted artifact schema

`src/tigrcorn/compat/interop_runner.py` now emits a standardized bundle shape for new independent-certification runs.

Required bundle files:

- `manifest.json`
- `summary.json`
- `index.json`

Required per-scenario files:

- `summary.json`
- `index.json`
- `result.json`
- `scenario.json`
- `command.json`
- `env.json`
- `versions.json`
- `wire_capture.json`

The runner also preserves the underlying logs and wire artifacts already produced by the interop flow, including packet traces, qlogs when applicable, transcripts, negotiation records, and stdout/stderr logs.

### 3. The validator now rejects incomplete bundles

`src/tigrcorn/compat/release_gates.py` now exposes independent-bundle validation helpers that reject incomplete proof bundles when required files or inventories are absent.

The new helpers are used for the Phase 9B proof bundle and are covered by negative tests.

### 4. A real proof bundle was generated into the new 0.3.9 release root

A real rerun of one already-green independent scenario now exists under:

- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-harness-foundation-bundle/`

That bundle contains a fresh rerun of:

- `http1-server-curl-client`

This preserves the same semantic claim as the current canonical independent matrix while proving that the new harness can generate a complete bundle in the new release layout without manual artifact patching.

## Validation result for this checkpoint

Current machine-readable truth:

- authoritative boundary: `True`
- strict target boundary: `False`
- promotion target: `False`
- proof bundle validator: `True`

The proof bundle is intentionally **not** the full strict-target release bundle. It is a reusable harness-foundation bundle with one proof scenario.

## Honest status after this checkpoint

This checkpoint does **not** close the remaining strict-target blockers.

After Phase 9B:

- the authoritative certification boundary remains green
- the strict target boundary remains red
- the package is still **not yet** certifiably fully featured under the stricter promotion profile
- the 13 missing strict-target independent scenarios are still missing as preserved third-party release artifacts
- the 7 public-flag/runtime blockers still remain
- the strict performance and promotion-gate hardening work still remain

What changed is the execution substrate:

- the repo now has a standardized wrapper registry
- the repo now has a standardized artifact schema for newly generated independent bundles
- the repo now has a validator that rejects incomplete bundles
- the repo now has a proof bundle under the reserved `0.3.9` release root showing the new harness is real
