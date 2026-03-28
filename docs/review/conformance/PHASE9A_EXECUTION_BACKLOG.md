# Phase 9A execution backlog

This document is the human-readable companion to `docs/review/conformance/phase9a_execution_backlog.current.json`.

It freezes the Phase 9A execution backlog so every remaining promotion blocker has an owner role, target phase, touch-file list, artifact contract, and exit-test definition.

## Owner roles

- `promotion_program_owner` — Owns the promotion contract, release-root policy, current-state truthfulness, and cross-stream coordination for the strict-promotion program.
- `interop_harness_owner` — Owns the reusable third-party scenario harness, artifact capture model, and matrix-entry preservation rules for independent certification.
- `websocket_interop_owner` — Owns RFC 7692 interop closure across HTTP/1.1, HTTP/2, and HTTP/3 WebSocket carriers.
- `semantic_http_owner` — Owns RFC 9110 bounded semantic closure for CONNECT, trailer fields, and content coding.
- `tls_revocation_owner` — Owns revocation and OCSP behavior, TLS policy wiring, and preserved independent evidence for RFC 6960.
- `tls_runtime_owner` — Owns TLS flag/runtime closure including cipher-policy semantics and package-owned handshake wiring.
- `observability_owner` — Owns logging, StatsD, OTEL, startup/shutdown behavior, and operator-facing observability exporters.
- `scheduler_runtime_owner` — Owns global concurrency admission, overload behavior, scheduler policy/runtime wiring, and correctness-under-load coverage.
- `websocket_runtime_owner` — Owns WebSocket keepalive policy, outbound ping scheduling, timeout-driven close behavior, and carrier parity.
- `performance_owner` — Owns the strict performance program, matrix lanes, SLO thresholds, artifact preservation, and platform declarations.
- `promotion_gate_owner` — Owns the composite evaluator, artifact validation, negative fixtures, and documentation/gate alignment.
- `release_assembly_owner` — Owns final 0.3.9 release-root assembly, bundle promotion, status snapshots, and release-note truthfulness.

## Strict-target independent-scenario backlog

There are **13** strict-target scenario rows.

| Scenario | RFC | Phase | Owner role | Current gap | Depends on |
| --- | --- | --- | --- | --- | --- |
| websocket-http11-server-websockets-client-permessage-deflate | RFC 7692 | 9C | websocket_interop_owner | missing_independent_preserved_artifact | 9B |
| websocket-http2-server-h2-client-permessage-deflate | RFC 7692 | 9C | websocket_interop_owner | missing_independent_preserved_artifact | 9B |
| websocket-http3-server-aioquic-client-permessage-deflate | RFC 7692 | 9C | websocket_interop_owner | missing_independent_preserved_artifact | 9B |
| http11-connect-relay-curl-client | RFC 9110 §9.3.6 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http2-connect-relay-h2-client | RFC 9110 §9.3.6 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http3-connect-relay-aioquic-client | RFC 9110 §9.3.6 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http11-trailer-fields-curl-client | RFC 9110 §6.5 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http2-trailer-fields-h2-client | RFC 9110 §6.5 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http3-trailer-fields-aioquic-client | RFC 9110 §6.5 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http11-content-coding-curl-client | RFC 9110 §8 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http2-content-coding-curl-client | RFC 9110 §8 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| http3-content-coding-aioquic-client | RFC 9110 §8 | 9D | semantic_http_owner | missing_independent_preserved_artifact | 9B |
| tls-server-ocsp-validation-openssl-client | RFC 6960 | 9E | tls_revocation_owner | missing_independent_preserved_artifact | 9B |

Each strict-target scenario row in the machine-readable backlog includes:

- the exact scenario ID
- the required release-root and bundle path
- the peer provenance kind and stack
- the module / fixture touch list
- the required preserved artifact files
- the peer assertions that must be visible in the preserved bundle
- the exit tests that must pass before the row is considered closed

## Public flag/runtime backlog

There are **7** public-flag closure rows.

| Flag | Current state | Phase | Owner role | Touch-file start |
| --- | --- | --- | --- | --- |
| --ssl-ciphers | parse_only | 9F | tls_runtime_owner | src/tigrcorn/cli.py, src/tigrcorn/config/load.py … |
| --log-config | parse_only | 9F | observability_owner | src/tigrcorn/cli.py, src/tigrcorn/config/load.py … |
| --statsd-host | parse_only | 9F | observability_owner | src/tigrcorn/cli.py, src/tigrcorn/config/load.py … |
| --otel-endpoint | parse_only | 9F | observability_owner | src/tigrcorn/cli.py, src/tigrcorn/config/load.py … |
| --limit-concurrency | parse_only | 9F | scheduler_runtime_owner | src/tigrcorn/cli.py, src/tigrcorn/config/load.py … |
| --websocket-ping-interval | partially_wired | 9F | websocket_runtime_owner | src/tigrcorn/cli.py, src/tigrcorn/config/load.py … |
| --websocket-ping-timeout | partially_wired | 9F | websocket_runtime_owner | src/tigrcorn/cli.py, src/tigrcorn/config/load.py … |

Each flag row in the machine-readable backlog includes:

- the current runtime state (`parse_only` or `partially_wired`)
- the module touch list
- the required unit-test and profile coverage
- the required runtime-state transition
- the exact operator/runtime claim that must become true
- the exit tests that must pass before the flag is promotion-ready

## Performance and gate-hardening contracts

The backlog also freezes:

- a Phase **9G** performance-closure contract
- a Phase **9H** promotion-gate hardening contract
- no-regression guards for the authoritative boundary, operator surface, and documentation truthfulness

## Release-root reminder

- immutable candidate root: `docs/review/conformance/releases/0.3.7/release-0.3.7/`
- reserved next promotable root: `docs/review/conformance/releases/0.3.9/release-0.3.9/`

This backlog does **not** claim the repository is already strict-target green. It freezes the execution contract needed to get there.
