# 0.3.6 consolidated release bundle

This release root consolidates the current evidence tiers for `tigrcorn` version 0.3.6.

- `tigrcorn-independent-certification-release-matrix/` is the canonical independent certification bundle.
- `tigrcorn-same-stack-replay-matrix/` preserves HTTP/3 and RFC 9220 regression artifacts that still rely on the package-owned replay client.
- `tigrcorn-mixed-compatibility-release-matrix/` preserves the legacy mixed bundle for compatibility and replay.

The canonical package-wide certification boundary remains `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.
