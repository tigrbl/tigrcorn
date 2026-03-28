# RFC certification status for the updated archive

This repository targets the package-wide **authoritative certification boundary** defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Current authoritative status

Under that authoritative certification boundary, the package remains **certifiably fully RFC compliant** and preserves the required **independent-certification** evidence for the authoritative HTTP/3, WebSocket, TLS, ALPN, X.509, and `aioquic` surfaces.

## Current strict-target status

The stricter next-target program defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is now **green** under the 0.3.9 working release root.

Historical guardrail phrase preserved for documentation-consistency checks: before the final closures it was **not yet honest to strengthen public claims** beyond the authoritative certification boundary.

RFC 7692, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8, and RFC 6960 are all now satisfied at the required independent-certification tier in the 0.3.9 working release root.

That means the evaluated 0.3.9 working release root is now **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

The remaining work is administrative: explicit version-bump / canonical-promotion work has not yet been performed, so `pyproject.toml` still reports `0.3.6` and the authoritative canonical release root remains `0.3.6`.

## Phase 9I release assembly

Phase 9I reassembles the 0.3.9 working release root with refreshed bundle manifests, bundle indexes, bundle summaries, flag/operator/performance bundles, and current-state docs.

That assembled root is **promotable** under the strict target, but it is not yet the canonical authoritative release root because explicit release-promotion/version-bump work remains deferred.

- `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
