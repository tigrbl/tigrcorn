# Current repository state — Phase 6 observability and export-surface checkpoint

This checkpoint records the mutable-tree Phase 6 observability closure work.

## What changed

- `src/tigrcorn/config/observability_surface.py` now defines the package-owned metric schema, exporter adapter versions, and qlog experimental/redaction contract.
- `src/tigrcorn/observability/metrics.py` now exposes stable transport, security, loss, and HTTP/3 counter families plus explicit StatsD/DogStatsD target parsing.
- `src/tigrcorn/observability/tracing.py` now emits the declared OTEL scope version instead of a phase-local placeholder.
- `src/tigrcorn/protocols/http3/handler.py` now feeds the public observability counters for QUIC sessions, datagrams, handshakes, Retry, early-data outcomes, path migration/challenge/response, QPACK stream creation, HTTP/3 requests, and GOAWAY observation.
- `src/tigrcorn/transports/quic/connection.py` now preserves package-owned loss/PTO totals so the runtime can surface them as stable operator counters.
- `src/tigrcorn/compat/interop_runner.py` now emits observer qlog files with explicit experimental/version markers and endpoint / connection-id redaction.
- Generated artifacts now exist at `docs/conformance/metrics_schema.json`, `docs/conformance/metrics_schema.md`, `docs/conformance/qlog_experimental.json`, `docs/conformance/qlog_experimental.md`, and `docs/ops/observability.md`.
- CI now regenerates the Phase 6 artifacts and runs `tests/test_phase6_observability_surface.py` together with `tests/test_phase9f2_logging_exporter_closure.py`.

## Claim status

- `TC-OBS-METRICS-SCHEMA` is now implemented in-tree.
- `TC-OBS-EXPORT-ADAPTERS` is now implemented in-tree.
- `TC-OBS-QLOG-EXPERIMENTAL` is now implemented in-tree.

## Current package truth

- The working tree still evaluates as **certifiably fully RFC compliant** under the authoritative certification boundary.
- The canonical `0.3.9` release root still evaluates as **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.
- Phase 6 artifacts are present in the mutable tree only; they are not yet frozen into a superseding versioned release root.

## Validation used for this checkpoint

- `python tools/cert/observability_surface.py`
- `python -m unittest tests.test_phase6_observability_surface`
- `python -m unittest tests.test_phase9f2_logging_exporter_closure`
- `python -m compileall -q src tools`

## Honest limitation

Remote GitHub required-check enforcement for the new Phase 6 tests still depends on GitHub-side ruleset and environment activation outside this repository tree.
