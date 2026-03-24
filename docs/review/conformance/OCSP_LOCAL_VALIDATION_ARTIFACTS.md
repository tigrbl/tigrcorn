# OCSP local validation artifacts

This document records the local OCSP validation vectors preserved during **Phase 9E**.

Artifact bundle:

- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-ocsp-local-validation-artifacts/`

The preserved vectors are:

- `ocsp-good-response-cache-reuse-client-auth`
- `ocsp-stale-response-require-fails`
- `ocsp-revoked-client-certificate-fails`
- `ocsp-unreachable-soft-fail-vs-require`

These vectors are not the third-party independent-certification proof. They exist to preserve local, reproducible evidence for the freshness, cache, revoked-certificate, and soft-fail / require branches that back the OpenSSL interop artifact.
