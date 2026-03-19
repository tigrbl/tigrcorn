# RFC hardening validation summary

Validation date: 2026-03-14

## Package changes validated

- public API exposes `ssl_ca_certs` and `ssl_require_client_cert`
- CLI exposes `--ssl-ca-certs` and `--ssl-require-client-cert`
- conformance corpus enumerates the full locally claimed RFC surface, including the QUIC-facing RFC 8446 TLS 1.3 subset
- QUIC / HTTP/3 documentation is reconciled with implemented client-certificate support
- README / conformance docs explicitly state that QUIC-TLS client-authentication is not a remaining blocker
- documentation reconciliation guards explicitly forbid stale mTLS boundary wording
- unified `external_matrix.current_release.json` parses correctly under the interop runner
- OpenSSL QUIC external client fixture accepts optional client-certificate parameters

## Test slices executed

### Packaging and documentation slice

```text
pytest -q \
  tests/test_cli_and_asgi3.py \
  tests/test_conformance_corpus.py \
  tests/test_documentation_reconciliation.py \
  tests/test_external_current_release_matrix.py \
  tests/test_config_matrix.py \
  tests/test_public_quic_tls_packaging.py
```

Result: 25 passed

### Conformance corpus completion slice

```text
pytest -q \
  tests/test_conformance_corpus.py \
  tests/test_documentation_reconciliation.py \
  tests/test_tls13_engine_upgrade.py
```

Result: 16 passed

### Adjacent release-matrix and QUIC/TLS regression slice

```text
pytest -q \
  tests/test_external_independent_peer_release_matrix.py \
  tests/test_external_rfc_hardening_candidate_matrix.py \
  tests/test_quic_tls_external_interop_regressions.py \
  tests/test_rfc_compliance_hardening.py
```

Result: 12 passed, 2 skipped


### Public mTLS surface verification slice

```text
pytest -q \
  tests/test_cli_and_asgi3.py \
  tests/test_public_api_cli_mtls_surface.py \
  tests/test_config_matrix.py \
  tests/test_public_quic_tls_packaging.py
```

Result: 18 passed

### Request-specific corpus verification slice

```text
pytest -q \
  tests/test_conformance_corpus.py \
  tests/test_documentation_reconciliation.py \
  tests/test_tls13_engine_upgrade.py
```

Result: 16 passed


### Documentation reconciliation hardening slice

```text
pytest -q tests/test_documentation_reconciliation.py
```

Result: 7 passed

## Honest certification boundary

This package is stronger than the supplied input archive, but it is still not honestly certifiable as a fully RFC-compliant package because preserved independent-peer HTTP/3 request/response and WebSocket-over-HTTP/3 artifacts are still not bundled.
