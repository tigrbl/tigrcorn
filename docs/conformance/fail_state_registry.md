# Fail-State Registry

This file is generated from the package-owned Phase 7 negative-certification metadata.

| Surface | Default action | Risk | Runtime contract | Observable outcomes |
|---|---|---|---|---|
| `proxy` | `strip_and_continue` | untrusted forwarded header spoofing | Untrusted Forwarded and X-Forwarded-* data is ignored and the connection continues using the transport-observed peer and scheme. | proxy view stays on transport peer, request proceeds without forwarded override |
| `early_data` | `reject_response` | replayed resumed request without admitted 0-RTT | When early-data policy is require and resumption succeeds without admitted early data, the package sends 425 Too Early before ASGI dispatch. | 425 Too Early, no ASGI app dispatch |
| `quic` | `close_connection` | invalid token, prohibited migration, or transport-integrity failure | QUIC transport failures produce Retry, CONNECTION_CLOSE, or transport-level close events instead of partially admitted application state. | retry event, close event, pending close datagram |
| `origin` | `reject_or_abort` | path traversal or invalid ASGI pathsend | Traversal attempts return 404 from the package-owned origin surface, while invalid http.response.pathsend inputs raise ASGIProtocolError. | 404 Not Found, ASGIProtocolError |
| `connect_relay` | `reject_response` | open relay or disallowed CONNECT target | Denied or allowlist-mismatched CONNECT requests terminate with 403 connect denied and do not dispatch to the ASGI app. | 403 connect denied, stream end / response completion |
| `tls_x509` | `abort_validation` | revoked, stale, or unreachable revocation state under strict validation | Strict X.509 revocation failures abort validation with ProtocolError rather than soft-admitting the peer. | ProtocolError, preserved OCSP validation artifacts |
| `mixed_topology` | `gate_reject` | evidence-tier drift or blocked scenario metadata in mixed and same-stack matrices | Promotion and release-gate evaluators fail closed when matrix metadata is blocked, pending, or outside the declared evidence tier. | release gate failure, promotion target failure |
