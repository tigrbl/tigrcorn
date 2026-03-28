# Documentation reconciliation update: QUIC mTLS boundary

This request-specific update tightens the documentation and the documentation guards around the QUIC / HTTP/3 client-authentication surface.

## Updated docs

- `docs/protocols/quic.md` now states explicitly that QUIC-TLS client-authentication is implemented, exposed through the public API / CLI, and not part of the remaining package-level blocker.
- `README.md` now states explicitly that the remaining certification boundary is limited to broader third-party HTTP/3 data-plane evidence rather than QUIC client-authentication.
- `docs/review/conformance/README.md` now states explicitly that QUIC-TLS client-authentication is not part of the remaining blocker in this archive.

## Hardened doc guard

`tests/test_documentation_reconciliation.py` now contains explicit assertions that:

- the README, conformance README, and QUIC protocol doc positively state that QUIC-TLS client-authentication is no longer a blocker
- stale mTLS wording is forbidden in those files
- the remaining boundary is pinned to missing third-party HTTP/3 request/response and WebSocket-over-HTTP/3 evidence
