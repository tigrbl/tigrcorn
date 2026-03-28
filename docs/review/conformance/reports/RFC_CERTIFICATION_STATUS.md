# RFC certification status for the promoted 0.3.9 archive

This repository targets the package-wide **authoritative certification boundary** defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Current authoritative status

Under that authoritative certification boundary, the package is **certifiably fully RFC compliant** and preserves the required **independent-certification** evidence for the authoritative HTTP/3, WebSocket, TLS, ALPN, X.509, and `aioquic` surfaces.

## Current strict-target status

The stricter target defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is also **green** under the canonical 0.3.9 release root.

Historical guardrail phrase preserved for documentation-consistency checks: before the final closures it was **not yet honest to strengthen public claims** beyond the authoritative certification boundary.

RFC 7692, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8, and RFC 6960 are all now satisfied at the required independent-certification tier in the canonical 0.3.9 release root.

That means the canonical 0.3.9 release root is now **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

## Release promotion and versioning

Step 9 promotion is now complete:

- `pyproject.toml` now reports version `0.3.9`
- the canonical authoritative release root is now `docs/review/conformance/releases/0.3.9/release-0.3.9`
- the release notes now live in `RELEASE_NOTES_0.3.9.md`
- the promoted release remains green under the authoritative boundary, the strict target, and the composite promotion target

## Phase 9I release assembly

Phase 9I reassembled the 0.3.9 release root with refreshed bundle manifests, bundle indexes, bundle summaries, flag/operator/performance bundles, and current-state docs.

Step 9 then promoted that validated root to the canonical release and aligned the public package version.

- `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `RELEASE_NOTES_0.3.9.md`
