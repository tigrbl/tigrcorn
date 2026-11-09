# Current repository state — Phase 5 origin delivery contract checkpoint

This checkpoint records the mutable Phase 5 origin/static/pathsend contract surface in the working tree.

What changed:

- added `src/tigrcorn/config/origin_surface.py` as the canonical metadata source for path resolution, file selection, HTTP semantics, and `http.response.pathsend`
- generated `docs/conformance/origin_contract.json`, `docs/conformance/origin_contract.md`, `docs/conformance/origin_negatives.json`, `docs/conformance/origin_negatives.md`, and `docs/ops/origin.md`
- hardened `src/tigrcorn/static.py` so decoded `..` segments and backslash-separated segments are denied instead of normalized into platform-specific traversal behavior
- hardened `src/tigrcorn/asgi/send.py` so `http.response.pathsend` requires an absolute existing regular file and snapshots the file length at dispatch time
- promoted implementation claims for the required `TC-CONTRACT-ORIGIN-*` rows in `docs/review/conformance/claims_registry.json`

What is now true:

- the package remains **certifiably fully RFC compliant** under the authoritative certification boundary
- the canonical `0.3.9` release root remains **strict-target certifiably fully RFC compliant** and **certifiably fully featured**
- origin/static/pathsend behavior is now explicitly documented for percent-decoding order, dot-segment and separator denial, mount-root and symlink containment, hidden-file posture, MIME derivation, directory-index behavior, validator and range mapping, HEAD parity, and `pathsend` mutation/disconnect races

What is not yet claimed by this checkpoint alone:

- the mutable Phase 5 artifacts have not yet been promoted into a new frozen release root
- GitHub-side required-check enforcement for the Phase 5 tests still depends on the remote ruleset and environment activation tracked in the Phase 0 checkpoint
