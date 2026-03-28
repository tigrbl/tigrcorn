> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Phase 4 Advanced Protocol and Delivery Checkpoint

This checkpoint closes advanced delivery features that stay inside the direct app-server/runtime boundary.

## Included feature lanes

- Early Hints
- Alt-Svc
- runtime compatibility and embedding helper
- static-file delivery hardening
- protocol-aware example packaging

## Excluded boundaries

- cache freshness policy
- digest/signature systems
- gateway caching/enforcement

See the current-state report and JSON status artifact for the repository's exact checkpoint truth. For the later boundary decision that formalizes RFC 8297 and the bounded RFC 7838 §3 surface, see `docs/review/conformance/PHASE4_RFC_BOUNDARY_FORMALIZATION.md`.


## Validation snapshot

- `python -m compileall -q src/tigrcorn`
- focused bundle: **62 passed, 0 failed**

See `phase4_advanced_protocol_delivery_checkpoint.current.json` for the precise checkpoint truth and file list.
