# Delivery notes for the certification update archive

This archive updates `tigrcorn` against the package-wide certification target documented in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## What was completed in this delivery

- installed and exercised the true third-party `aioquic` certification runtime in the update environment
- regenerated and promoted preserved passing artifacts for the nine previously missing independent HTTP/3 / RFC 9220 scenarios
- enabled those scenarios in `docs/review/conformance/external_matrix.release.json`
- refreshed `docs/review/conformance/release_gate_status.current.json` and `docs/review/conformance/RELEASE_GATE_STATUS.md` to reflect the green release-gate result
- updated `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`, `docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md`, `docs/review/conformance/reports/RFC_HARDENING_REPORT.md`, `docs/review/conformance/README.md`, and `docs/review/conformance/INDEPENDENT_HTTP3_CERTIFICATION_STATE.md` to describe the new current state honestly
- corrected the third-party RFC 9220 adapter so it decodes server frames in client mode and drives the CONNECT stream in the same message / echo pattern as the package-owned H3 WebSocket client
- fixed the runtime interoperability issues that prevented honest third-party HTTP/3 artifact generation:
  - QUIC Initial receive-key derivation across Retry and direction changes
  - HTTP/3 server control-stream / SETTINGS emission timing
  - QUIC STREAM LEN / OFF parsing and emission
  - compact QUIC session-ticket encoding for resumption interop
  - original-length ClientHello PSK binder hashing and verification

## Current honest status

Under the authoritative boundary in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, this archive is now **certifiably fully RFC compliant**.

The stricter non-authoritative all-surfaces-independent overlay remains incomplete, and the preserved provisional bundles remain in-tree as historical / planning aids. Those items do not change the passing authoritative release-gate result.

## Validation performed for this checkpoint

- `PYTHONPATH=src:. python -c "from tigrcorn.compat.release_gates import evaluate_release_gates; report = evaluate_release_gates('.'); print(report.passed, len(report.failures))"` → `True 0`
- `PYTHONPATH=src:. pytest -q tests/test_documentation_reconciliation.py tests/test_release_gates.py tests/test_certification_policy_alignment.py tests/test_external_current_release_matrix.py tests/test_external_independent_peer_release_matrix.py tests/test_external_interop_runner_matrix.py tests/test_provisional_http3_gap_bundle.py tests/test_provisional_all_surfaces_gap_bundle.py tests/test_scheduler_runtime.py tests/test_provisional_flow_control_gap_bundle.py tests/test_intermediary_proxy_corpus.py -rs` → `32 passed, 2 skipped`
- `PYTHONPATH=src:. pytest -q tests/test_tls13_engine_upgrade.py tests/test_quic_tls_rfc9001.py tests/test_quic_transport_runtime_completion.py tests/test_http3_rfc9114.py tests/test_http3_websocket_rfc9220.py tests/test_quic_packets_rfc9000.py tests/test_quic_recovery_rfc9002.py tests/test_qpack_completion.py tests/test_aioquic_adapter_helpers.py` → `46 passed`
