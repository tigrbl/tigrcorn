> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Phase 2 Core HTTP Entity Semantics Checkpoint

This checkpoint closes the direct-server Phase 2 work that was previously identified as missing or partial:

- conditional requests
- server-generated validators for complete direct responses
- byte ranges and partial content
- HEAD/body metadata alignment across H1/H2/H3
- static-file direct support for validators and partial content

The implementation in this checkpoint deliberately stays inside the server/runtime boundary and deliberately avoids:

- cache freshness policy engines
- stale revalidation policy
- digest/signature trust surfaces
- gateway enforcement features

See the root current-state report for the detailed implementation and validation summary:

- `docs/review/conformance/state/checkpoints/CURRENT_REPOSITORY_STATE_PHASE2_CORE_HTTP_ENTITY_SEMANTICS_CHECKPOINT.md`
