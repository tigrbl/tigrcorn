# Phase 9E OCSP independent-certification closure

This checkpoint executes **Phase 9E** of `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`.

It advances the strict-target closure for **RFC 6960** by preserving a live **OpenSSL-backed** OCSP validation artifact in the 0.3.8 working release root.

## What changed in this checkpoint

### 1. Deterministic OCSP fixtures now exist

The repository now ships a deterministic OCSP fixture module and helper launcher paths for the 9E work:

- `tests/fixtures_pkg/interop_ocsp_fixtures.py`
- `tests/fixtures_pkg/ocsp_listener_launcher.py`
- `tests/fixtures_pkg/external_openssl_tls_client.py`

Those fixtures provide:

- a deterministic root CA and issuer CA
- a server leaf certificate for `localhost`
- a good client certificate with an OCSP AIA URL
- a revoked client certificate with an OCSP AIA URL
- a stale-response client certificate with an OCSP AIA URL
- a local HTTP OCSP responder that records fetch counts and request metadata

### 2. The independent matrix now contains the RFC 6960 third-party scenario

The canonical independent matrix now declares:

- `tls-server-ocsp-validation-openssl-client`

That row uses:

- a package-owned live listener configured for mTLS and `--ssl-ocsp-mode require`
- a third-party OpenSSL TLS client wrapper
- a deterministic OCSP responder returning a valid `GOOD` response for the client certificate

### 3. The 0.3.8 working release root now carries a passing OCSP artifact

The canonical working independent bundle under:

- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-independent-certification-release-matrix`

now contains a preserved OpenSSL OCSP validation artifact with this status:

- `tls-server-ocsp-validation-openssl-client` — **passed**

The preserved artifact records that:

- the third-party OpenSSL client completed the TLS handshake
- the live listener accepted the request only after the client certificate was validated
- the local OCSP responder was contacted during validation
- the client reached the HTTP layer and received `HTTP/1.1 200 OK`

### 4. Local OCSP validation vectors are now preserved

This checkpoint also preserves local validation vectors under:

- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-ocsp-local-validation-artifacts/`

Those vectors cover:

- good-response cache reuse for client-auth validation
- stale OCSP response failure in `require` mode
- revoked client certificate failure in `require` mode
- responder-unavailable `soft-fail` vs `require` divergence

## Runtime and validation surfaces covered here

This checkpoint validates the following OCSP / revocation behavior:

- live listener enforcement of `require`-mode OCSP policy for client certificates
- mTLS acceptance only when a good OCSP response is available
- stable cache-reuse semantics for repeated client-auth validation
- stale-response rejection
- revoked-client rejection
- unreachable-responder `soft-fail` / `require` divergence

Primary runtime areas for this work are:

- `src/tigrcorn/security/tls.py`
- `src/tigrcorn/security/policies.py`
- `src/tigrcorn/security/x509/path.py`
- related config model / normalize / validate paths

## Honest current result

This checkpoint does **not** make the repository strict-target complete or certifiably fully featured.

What is true now:

- the authoritative boundary remains green
- the RFC 6960 independent third-party OpenSSL OCSP artifact is now preserved and passing
- the strict boundary still fails because the remaining HTTP/3 third-party scenarios are preserved but not passing in this environment
- the composite promotion target still fails only because the remaining HTTP/3 CONNECT, trailer-fields, and content-coding scenarios are still preserved as non-passing artifacts

## Why the strict target is still not complete

RFC 6960 is no longer a missing-evidence blocker.

The strict target is still blocked by the three preserved-but-failing HTTP/3 third-party scenarios for CONNECT, trailer fields, and content coding:

- `http3-connect-relay-aioquic-client`
- `http3-content-coding-aioquic-client`

Those three scenarios remain preserved as failing artifacts in the 0.3.8 working release root and have not yet been refreshed from successful third-party `aioquic` runs.
