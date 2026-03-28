# Next development targets

This document tracks the **post-promotion in-bounds backlog** for the current `tigrcorn` package boundary.

It is governed by:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md` — authoritative in-bounds statement
- `docs/review/conformance/certification_boundary.json` — authoritative per-RFC evidence policy
- `docs/review/conformance/BOUNDARY_NON_GOALS.md` — authoritative out-of-bounds statement

This document does **not** broaden the current package claim. It tracks only the remaining in-bounds work selected from `tigrcorn_unified_policy_matrix.md` after removing items that are already complete and items that are explicitly out of bounds.

## Current baseline

The repository starts this checkpoint from a green promoted baseline:

- `evaluate_release_gates('.')` is green
- the preserved stricter target in `STRICT_PROFILE_TARGET.md` is green under the canonical `0.3.9` release root
- `evaluate_promotion_target('.')` is green
- under the canonical `0.3.9` boundary and release root, the package is certifiably fully RFC compliant and certifiably fully featured

## Historical strict-promotion compatibility note

This document now tracks the post-promotion in-bounds backlog, but older promotion checks still require the preserved strict-promotion guardrail phrases below. They are retained here as **archival compatibility phrases only** and do not redefine the current boundary or backlog:

- current authoritative boundary remains green
- 0.3.7 root is a candidate only
- new release root
- three-stream closure program
- strict RFC evidence closure
- family-flag contract/runtime closure
- throughput/latency closure with RFC-correctness-under-load
- No public doc is allowed to strengthen package claims until the strict target is actually green.
- `docs/review/conformance/STRICT_PROFILE_TARGET.md`

## Already normalized in the current checkpoint

The following governance items are now treated as complete and are **not** active backlog items anymore:

- one canonical T/P/A/D/R in-bounds boundary statement
- one canonical out-of-bounds statement
- one explicit supported runtime statement (`auto`, `asyncio`, `uvloop`)
- one explicit statement that parser/backend selection, WebSocket engine pluggability, and alternate app-interface pluggability are outside the current public surface

## Active in-bounds next targets

### [A][D][R] Static and file-delivery surface completion

This backlog slice is complete in the current checkpoint:

- server-native static route / mount controls are implemented
- explicit static directory-to-file / index policy controls are implemented
- explicit static expiration controls are implemented
- standard ASGI `http.response.pathsend` is implemented
- CLI / config / env / docs / help / manifests are reconciled for the static delivery surface

### [P][R] WebSocket and HTTP/1.1 operator-surface completion

This backlog slice is complete in the current checkpoint:

- `--websocket-max-queue` is implemented and wired across HTTP/1.1, HTTP/2, and HTTP/3 WebSocket carriers
- the package-owned HTTP/1 parser incomplete-event cap is implemented as `--http1-max-incomplete-event-size`
- `--http1-buffer-size` is implemented
- `--http1-header-read-timeout` is implemented
- `--http1-keep-alive` / `--no-http1-keep-alive` are implemented
- CLI / config / env / docs / help / manifests are reconciled for the Phase 3 surface

### [P][R] HTTP/2 operator-surface completion

This backlog slice is complete in the current checkpoint:

- `--http2-max-concurrent-streams` is implemented
- `--http2-max-headers-size` is implemented
- `--http2-max-frame-size` is implemented
- `--http2-adaptive-window` / `--no-http2-adaptive-window` are implemented
- `--http2-initial-connection-window-size` and `--http2-initial-stream-window-size` are implemented
- `--http2-keep-alive-interval` and `--http2-keep-alive-timeout` are implemented
- CLI / config / env / docs / help / manifests are reconciled for the Phase 4 surface

### [T][R] TLS and revocation material surface completion

This backlog slice is complete in the current checkpoint:

- encrypted private-key password support is implemented as `--ssl-keyfile-password`
- direct local CRL material input is implemented as `--ssl-crl`
- CLI / config / env / validation / runtime / docs / manifests are reconciled for the TLS material-input surface

### [A][R] Lifecycle and embedder contract publication

This backlog slice is complete in the current checkpoint:

- the public lifecycle hook contract, signatures, ordering, and failure semantics are documented
- the public `EmbeddedServer` / programmatic serve contract is documented with examples
- the lifecycle/embedder contract remains inside the current ASGI3 hosting boundary and does not broaden the app-interface boundary

### [R] Documentation, manifest, and current-state parity

This backlog slice is complete in the current checkpoint:

- README / `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` / `CURRENT_STATE_CHAIN.md` / flag docs / JSON manifests / CLI help snapshots are aligned with the implemented public surface
- landed backlog items are recorded in current-state docs and machine-readable checkpoint state
- the rule that peer deltas do not automatically become product obligations unless they stay inside the canonical T/P/A/D/R boundary is preserved

## Current selected in-bounds backlog status

The selected in-bounds backlog from `tigrcorn_unified_policy_matrix.md` is now complete for the current T/P/A/D/R boundary and the explicit exclusions governed by `docs/review/conformance/BOUNDARY_NON_GOALS.md`.

## Explicit exclusions from this backlog

This backlog does **not** authorize implementation of the items that are explicitly out of bounds in `docs/review/conformance/BOUNDARY_NON_GOALS.md`, including:

- Trio runtime
- RFC 9218 prioritization
- RFC 9111 caching/freshness
- RFC 9530 digest fields
- RFC 9421 signatures
- JOSE / COSE
- parser/backend pluggability
- WebSocket engine pluggability
- alternate app-interface pluggability
- broader loop/topology/task-engine pluggability
- TLS minimum-version downgrade controls outside the current package posture

## Completion rule

The next development targets are complete only when each landed in-bounds item is reflected consistently across:

- code
- CLI/config/env validation
- public docs
- machine-readable manifests / flag contracts / current-state artifacts
- tests and release-gate validation

Until those items land, the package remains green for the current canonical `0.3.9` boundary, while still remaining incomplete against the broader unified-policy backlog.
