# Delivery notes — Phase 9I release assembly and certifiable checkpoint

This checkpoint reassembles the 0.3.8 working release root with refreshed bundle manifests, bundle indexes, bundle summaries, and machine-readable status snapshots.

- release-root manifest: `docs/review/conformance/releases/0.3.8/release-0.3.8/manifest.json`
- release-root bundle index: `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_index.json`
- release-root bundle summary: `docs/review/conformance/releases/0.3.8/release-0.3.8/bundle_summary.json`

All four previously failing HTTP/3 strict-target scenarios are now preserved as passing artifacts in the assembled 0.3.8 working release root.

Validation summary is recorded in `docs/review/conformance/phase9i_release_assembly.current.json`. Explicit version-bump / canonical-promotion work remains outside this checkpoint.
