# QUIC mTLS public API / CLI verification

This update verifies that the QUIC/TLS client-certificate controls are not only implemented in the lower configuration and transport layers, but are also reachable through the supported public entry points.

## Verified public surface

- `tigrcorn.api.serve()` accepts and forwards `ssl_ca_certs` and `ssl_require_client_cert`
- `tigrcorn.api.serve_import_string()` accepts and forwards the same parameters
- `tigrcorn.api.run()` forwards those parameters for both import-string and in-memory ASGI app entry paths
- `tigrcorn.cli.main()` builds a `ServerConfig` and forwards `--ssl-ca-certs` and `--ssl-require-client-cert` through the config-driven `run_config(...)` path
- `README.md` now shows the top-level Python API example alongside the CLI example for UDP / HTTP/3 client-certificate verification

## Added verification coverage

- `tests/test_public_api_cli_mtls_surface.py`

These tests are intentionally package-surface focused. They do not re-verify the QUIC/TLS certificate machinery itself; that is already covered by the existing runtime integration tests in `tests/test_public_quic_tls_packaging.py`.

## Honest certification note

This closes the quoted package-surface gap around QUIC mutual-TLS exposure on the public API and CLI.

It still does not eliminate the separate remaining certification blocker around bundled independent-peer HTTP/3 request/response and WebSocket-over-HTTP/3 evidence.
