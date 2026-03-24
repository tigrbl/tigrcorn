# Content-coding local behavior artifacts

This document records the local content-coding behavior vectors preserved during **Phase 9D3**.

Artifact bundle:

- `docs/review/conformance/releases/0.3.8/release-0.3.8/tigrcorn-content-coding-local-behavior-artifacts/`

The preserved vectors are:

- `http11-content-coding-gzip-pass`
- `http11-content-coding-identity-forbidden-406`
- `http11-content-coding-strict-unsupported-406`
- `http2-content-coding-gzip-pass`
- `http2-content-coding-identity-forbidden-406`
- `http2-content-coding-strict-unsupported-406`
- `http3-content-coding-gzip-pass`
- `http3-content-coding-identity-forbidden-406`
- `http3-content-coding-strict-unsupported-406`

These vectors are not part of the independent-certification proof tier. They preserve local correctness evidence for parity, identity-only failure semantics, and strict failure semantics while the third-party HTTP/3 proof path remains blocked by the missing `aioquic` runtime.
