# Phase 9 implementation plan

> **Update:** Phase 9A is now executed in-tree through `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`, `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md`, `docs/review/conformance/phase9a_promotion_contract.current.json`, and `docs/review/conformance/phase9a_execution_backlog.current.json`. The remaining critical path now starts at Phase 9B, while the frozen 9A contract remains the governing execution baseline.

This document is the detailed phase-by-phase implementation plan for turning the current Phase 8 strict-promotion target into a release-green, certifiably fully featured, and certifiably fully RFC compliant package under both:

- the current authoritative boundary in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- the stricter promotion target in `docs/review/conformance/STRICT_PROFILE_TARGET.md`

It is a planning and execution document. It is **not** a claim that the current tree is already strict-target complete.

## Current truth at the start of Phase 9

The current repository state is:

- authoritative boundary: green
- strict target boundary: blocked by 10 still-missing independent third-party scenarios plus 1 preserved failing RFC 7692 HTTP/3 artifact
- flag surface: blocked by 7 non-promotion-ready public flags
- operator surface: green
- performance target: blocked by stricter SLO and lane gaps
- documentation / claim consistency: green
- composite promotion gate: blocked

The 14 RFC targets already complete at the stricter target are:

- RFC 9112
- RFC 9113
- RFC 9114
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 7541
- RFC 9204
- RFC 6455
- RFC 8441
- RFC 9220
- RFC 8446
- RFC 5280
- RFC 7301

The 5 RFC surfaces still blocking the strict target are:

- RFC 7692
- RFC 9110 §9.3.6
- RFC 9110 §6.5
- RFC 9110 §8
- RFC 6960

The 7 public flags still blocking the promotion target are:

- `--ssl-ciphers`
- `--log-config`
- `--statsd-host`
- `--otel-endpoint`
- `--limit-concurrency`
- `--websocket-ping-interval`
- `--websocket-ping-timeout`

The current strict-promotion work therefore remains a **three-stream closure program**:

1. strict RFC evidence closure
2. public flag contract/runtime closure
3. strict performance and promotion-gate closure

## Phase sequencing rules

1. Do **not** mutate `docs/review/conformance/releases/0.3.7/release-0.3.7/`.
2. Assemble the promotable release under a **new** root such as `docs/review/conformance/releases/0.3.9/release-0.3.9/`.
3. Keep public claims pinned to the authoritative boundary until the strict target is genuinely green.
4. Do not expand the package boundary to RFC 7232 / RFC 9530 / RFC 9111 / RFC 9421 until the current strict target is closed.
5. Use package-owned local tests for rapid iteration, but require preserved third-party artifacts before claiming strict RFC closure.
6. Treat performance closure as a release program with live-listener and correctness-under-load evidence, not as a single benchmark script.

## Phase overview

| Phase | Goal | Primary blockers closed |
|---|---|---|
| 9A | Freeze the exact promotion contract and create the execution backlog | ambiguity in semantics / artifacts |
| 9B | Build reusable independent-certification harness plumbing | artifact capture / repeatability |
| 9C | Close RFC 7692 at independent-certification tier | 3 missing WebSocket compression scenarios |
| 9D | Close RFC 9110 bounded semantic surfaces at independent tier | 9 missing CONNECT / trailers / content-coding scenarios |
| 9E | Close RFC 6960 at independent-certification tier | 1 missing OCSP scenario |
| 9F | Close the 7 remaining public flag/runtime gaps | flag-surface blockers |
| 9G | Upgrade Phase 6 into the strict performance target | performance blockers |
| 9H | Harden the promotion evaluator so it cannot false-pass | evaluator under-enforcement |
| 9I | Assemble the new release root and cut the certifiable checkpoint | final promotion gate |
| 10 | Optional post-promotion boundary expansion | RFC 7232 / RFC 9530 and beyond |

## Phase 9A — freeze the promotion contract

### Objective

Remove ambiguity before implementation begins so every remaining blocker has a precise contract, owner, artifact model, and exit test.

### Work items

1. Freeze the next promotable release path as `docs/review/conformance/releases/0.3.9/release-0.3.9/`.
2. Create a tracker row for each of the 13 missing strict-target scenarios.
3. Create a tracker row for each of the 7 non-closed public flags.
4. Freeze the exact strict performance target fields from `docs/review/performance/performance_slos.json`.
5. Freeze the acceptance rule that the operator surface is already complete and must not regress.
6. Freeze the rule that RFC 7232, RFC 9530, RFC 9111, RFC 9421, JOSE, and COSE remain out-of-scope for the promotion-critical path.

### Files and modules to update

- `docs/review/conformance/STRICT_PROFILE_TARGET.md`
- `docs/review/conformance/FLAG_CERTIFICATION_TARGET.md`
- `docs/review/performance/PERFORMANCE_SLOS.md`
- `docs/review/conformance/promotion_gate.target.json`
- `docs/review/conformance/flag_contracts.json`
- `docs/review/conformance/flag_covering_array.json`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`

### Deliverables

- one issue or checklist row per missing scenario and per missing flag
- a frozen release-root decision
- explicit owner assignment for RFC, runtime, observability, scheduler, performance, and release-gate workstreams

### Exit criteria

- every remaining blocker maps to a concrete owner and deliverable
- no promotion-critical surface still depends on an undefined behavior contract

## Phase 9B — shared independent-certification harness foundation

### Objective

Build the reusable harness and artifact plumbing needed for the missing third-party scenarios so the repo stops treating each gap as an ad-hoc one-off.

### Work items

1. Standardize scenario execution wrappers for:
   - `curl`
   - `websockets`
   - `h2`
   - `aioquic`
   - `openssl`
2. Standardize artifact capture for every independent scenario:
   - `summary.json`
   - `index.json`
   - peer version metadata
   - command lines
   - environment snapshot
   - wire captures / logs where applicable
   - pass/fail result record
3. Add negative tests proving a scenario is rejected when required artifact files are absent or incomplete.
4. Validate that one already-green scenario can be rerun into the new 0.3.9 layout without changing its semantic claim.

### Files and modules to update

- `docs/review/conformance/external_matrix.release.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/` (new)
- `tools/` scenario runners and artifact-capture helpers
- `src/tigrcorn/compat/release_gates.py`
- new or expanded interop tests under `tests/`

### Deliverables

- reusable third-party harness wrappers
- a promoted artifact schema for the new release root
- at least one proof scenario generated into the new release layout

### Exit criteria

- the repo can generate and validate a full independent-certification scenario bundle without manual artifact patching

## Phase 9C — RFC 7692 independent-certification closure

### Objective

Promote WebSocket permessage-deflate from package-owned local/runtime support to preserved independent-certification evidence across all three carriers.

### Missing scenarios to close

- `websocket-http11-server-websockets-client-permessage-deflate`
- `websocket-http2-server-h2-client-permessage-deflate`
- `websocket-http3-server-aioquic-client-permessage-deflate`

### Work items

1. Verify the negotiation path on all carriers preserves:
   - extension advertisement only when enabled
   - valid offer/accept parsing
   - compressed echo correctness
   - clean fallback when the peer does not negotiate the extension
2. Preserve positive artifacts from third-party peers for HTTP/1.1, HTTP/2, and HTTP/3.
3. Preserve negative artifacts for malformed or unsupported offers locally so regressions are caught before interop reruns.
4. Update the strict target matrix so these scenarios resolve at `independent_certification` instead of `local_conformance`.

### Runtime modules most likely to change

- `src/tigrcorn/protocols/websocket/extensions.py`
- `src/tigrcorn/protocols/websocket/handler.py`
- `src/tigrcorn/protocols/http2/websocket.py`
- `src/tigrcorn/protocols/http3/websocket.py`
- `src/tigrcorn/config/model.py`
- `src/tigrcorn/config/validate.py`

### Test additions

- positive interop tests per carrier
- malformed-offer negative tests
- regression tests for no-compression fallback

### Exit criteria

- all 3 RFC 7692 scenarios are present in `external_matrix.release.json`
- all 3 have preserved passing third-party artifacts under the new release root
- the strict boundary no longer falls back to local-only evidence for RFC 7692

## Phase 9D — RFC 9110 bounded semantic closure at independent tier

### Objective

Promote the already-implemented bounded RFC 9110 surfaces from local conformance to preserved third-party independent certification.

### Missing scenarios to close

#### CONNECT relay

- `http11-connect-relay-curl-client`
- `http2-connect-relay-h2-client`
- `http3-connect-relay-aioquic-client`

#### Trailer fields

- `http11-trailer-fields-curl-client`
- `http2-trailer-fields-h2-client`
- `http3-trailer-fields-aioquic-client`

#### Content coding

- `http11-content-coding-curl-client`
- `http2-content-coding-curl-client`
- `http3-content-coding-aioquic-client`

### Workstream 9D1 — CONNECT relay

#### Tasks

1. Build a deterministic relay-target fixture and tunnel-echo peer.
2. Preserve independent artifacts for allowed relay behavior.
3. Preserve local negative tests for deny and allowlist rejection semantics.
4. Validate protocol-correct stream closure and error behavior on all carriers.

#### Likely modules

- `src/tigrcorn/protocols/connect.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `src/tigrcorn/protocols/http3/handler.py`
- `src/tigrcorn/config/model.py`
- `src/tigrcorn/config/validate.py`

### Workstream 9D2 — trailer fields

#### Tasks

1. Preserve request-trailer behavior for `pass`, `drop`, and `strict` locally.
2. Preserve independent third-party artifacts showing trailer exposure on HTTP/1.1, HTTP/2, and HTTP/3.
3. Validate end-of-message framing, stream shutdown, and ASGI trailer event exposure.

#### Likely modules

- `src/tigrcorn/asgi/receive.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `src/tigrcorn/protocols/http3/handler.py`
- `src/tigrcorn/protocols/http1/serializer.py`

### Workstream 9D3 — content coding

#### Tasks

1. Preserve third-party evidence for `Accept-Encoding` negotiation and `Content-Encoding` selection.
2. Validate `Vary: accept-encoding` behavior on the RFC-scoped path.
3. Preserve local negative tests for `identity-only` and `strict` policy failures.
4. Validate carrier parity across HTTP/1.1, HTTP/2, and HTTP/3.

#### Likely modules

- `src/tigrcorn/protocols/content_coding.py`
- `src/tigrcorn/asgi/send.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `src/tigrcorn/protocols/http3/handler.py`

### Exit criteria

- all 9 missing RFC 9110 bounded-semantic scenarios are preserved as passing third-party artifacts
- RFC 9110 §9.3.6, §6.5, and §8 all resolve at `independent_certification`

## Phase 9E — RFC 6960 independent-certification closure

### Objective

Promote OCSP/revocation behavior from local conformance to preserved independent-certification evidence.

### Missing scenario to close

- `tls-server-ocsp-validation-openssl-client`

### Work items

1. Build deterministic CA / issuer / leaf / responder fixtures for mTLS and revocation validation.
2. Preserve a third-party `openssl` scenario proving the package-owned TLS listener enforces the configured OCSP policy honestly.
3. Preserve local negative tests for:
   - stale OCSP responses
   - revoked client certificate
   - responder-unavailable soft-fail vs require behavior
4. Verify cache and freshness behavior so the independent artifact is backed by repeatable local correctness tests.

### Runtime modules most likely to change

- `src/tigrcorn/security/tls.py`
- `src/tigrcorn/security/policies.py`
- `src/tigrcorn/security/x509/path.py`
- `src/tigrcorn/config/model.py`
- `src/tigrcorn/config/normalize.py`
- `src/tigrcorn/config/validate.py`

### Exit criteria

- the `openssl` OCSP scenario is preserved under the new release root
- RFC 6960 resolves at `independent_certification`
- soft-fail and require semantics are locally regression-tested

## Phase 9F — public flag contract/runtime closure

### Objective

Turn the 7 non-promotion-ready public flags into fully wired, test-backed, documented operator or hybrid surfaces.

## Workstream 9F1 — TLS cipher-policy closure

### Blocking flag

- `--ssl-ciphers`

### Tasks

1. Define a precise public contract for the flag:
   - supported naming syntax
   - TLS-version applicability
   - TCP/TLS and QUIC/TLS behavior
2. Add a runtime field to the resolved listener config so the flag is not lost after config normalization.
3. Implement package-owned cipher-suite selection in the TLS 1.3 handshake path instead of parse-only config storage.
4. Validate that unsupported cipher expressions fail fast and do not silently downgrade to defaults.
5. Add tests proving the configured allowlist changes the negotiated suite.

### Likely modules

- `src/tigrcorn/cli.py`
- `src/tigrcorn/config/load.py`
- `src/tigrcorn/config/model.py`
- `src/tigrcorn/config/normalize.py`
- `src/tigrcorn/config/validate.py`
- `src/tigrcorn/security/tls.py`
- `src/tigrcorn/security/tls13/extensions.py`
- `src/tigrcorn/security/tls13/handshake.py`

## Workstream 9F2 — logging and exporter closure

### Blocking flags

- `--log-config`
- `--statsd-host`
- `--otel-endpoint`

### Tasks

1. Make `--log-config` a real runtime input to `configure_logging()`.
2. Freeze precedence rules between `--log-config`, `--log-level`, `--structured-log`, `--access-log-file`, and `--error-log-file`.
3. Implement a real StatsD exporter path instead of only exposing `render_statsd()`.
4. Implement a real OTEL export path and freeze its exact contract.
5. Add lifecycle handling, failure-mode tests, and deployment-profile coverage for exporter startup and shutdown.

### Likely modules

- `src/tigrcorn/cli.py`
- `src/tigrcorn/config/load.py`
- `src/tigrcorn/config/model.py`
- `src/tigrcorn/config/normalize.py`
- `src/tigrcorn/observability/logging.py`
- `src/tigrcorn/observability/metrics.py`
- `src/tigrcorn/observability/tracing.py`
- `src/tigrcorn/server/runner.py`

## Workstream 9F3 — concurrency and WebSocket keepalive closure

### Blocking flags

- `--limit-concurrency`
- `--websocket-ping-interval`
- `--websocket-ping-timeout`

### Tasks

1. Freeze `--limit-concurrency` semantics as a global in-flight admission cap across supported protocols.
2. Add the limit to the live scheduler policy and enforce it at request / stream / task admission rather than only at parse time.
3. Define protocol-specific overload behavior:
   - HTTP/1.1 rejection response
   - HTTP/2 refusal behavior
   - HTTP/3 refusal behavior
   - WebSocket admission refusal behavior
4. Convert `KeepAlivePolicy` from a passive helper into a live runtime subsystem.
5. Schedule outbound ping frames on HTTP/1.1, HTTP/2, and HTTP/3 WebSocket carriers.
6. Enforce `ping_timeout` with deterministic session close behavior and metrics.
7. Add correctness-under-load performance profiles because these are hybrid, not pure-operator, controls.

### Likely modules

- `src/tigrcorn/cli.py`
- `src/tigrcorn/config/load.py`
- `src/tigrcorn/config/model.py`
- `src/tigrcorn/config/validate.py`
- `src/tigrcorn/flow/keepalive.py`
- `src/tigrcorn/scheduler/policy.py`
- `src/tigrcorn/scheduler/runtime.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/websocket/handler.py`
- `src/tigrcorn/protocols/http2/websocket.py`
- `src/tigrcorn/protocols/http3/websocket.py`
- `src/tigrcorn/observability/metrics.py`

### Exit criteria for Phase 9F

- all current public flag strings are promotion-ready
- `evaluate_promotion_target(...).flag_surface.passed` is true
- every hazard cluster in `flag_covering_array.json` has passing coverage for the affected flags

## Phase 9G — strict performance target closure

### Objective

Upgrade the Phase 6 performance harness into the stricter promotion-grade performance program.

### Required metric additions

- `p99_9_ms`
- `time_to_first_byte_ms`
- `handshake_latency_ms`
- `protocol_stalls`

### Required threshold additions

- `max_p50_ms`
- `max_p95_ms`
- `max_p99_9_ms`
- `max_time_to_first_byte_ms`
- `max_handshake_latency_ms`
- `max_protocol_stalls`
- `max_rss_kib`
- `max_scheduler_rejections`

### Required relative-budget additions

- `max_p99_9_increase_fraction`
- `max_cpu_increase_fraction`
- `max_rss_increase_fraction`

### Work items

1. Extend `perf_runner` to emit the missing metrics.
2. Add true matrix lanes:
   - `component_regression`
   - `end_to_end_release`
3. Define credible thresholds per profile instead of placeholder-style bounds.
4. Preserve `correctness.json` for every RFC-scoped and hybrid profile.
5. Add live-listener end-to-end profiles for:
   - HTTP/1.1
   - HTTP/2
   - HTTP/3
   - WebSocket
   - CONNECT relay
   - trailer fields
   - content coding
   - TLS / mTLS / OCSP
   - observability overhead
   - overload / scheduler controls
6. Record certification platforms and tie thresholds to those platforms.

### Likely modules and files

- `src/tigrcorn/compat/perf_runner.py`
- `tools/run_perf_matrix.py`
- `benchmarks/`
- `docs/review/performance/PERFORMANCE_SLOS.md`
- `docs/review/performance/performance_slos.json`
- `docs/review/performance/performance_matrix.json`
- `docs/review/performance/artifacts/`

### Exit criteria

- `evaluate_promotion_target(...).performance.passed` is true
- every required metric, threshold, budget, artifact, and lane is present and validated
- correctness-under-load passes for all RFC-scoped and hybrid profiles

## Phase 9H — promotion-evaluator hardening

### Objective

Close the remaining gap where the strict performance target is documented more strongly than the current evaluator enforces.

### Work items

1. Make the promotion evaluator enforce all required artifact files, including `correctness.json`.
2. Make it enforce required matrix lanes.
3. Make it enforce certification-platform declarations.
4. Make it enforce documented SLOs per profile.
5. Add negative tests for every missing-key and missing-file failure path.
6. Ensure documentation checks remain honest and do not strengthen claims before the gate is truly green.

### Likely modules and files

- `src/tigrcorn/compat/release_gates.py`
- `tests/test_release_gates.py`
- `tests/test_phase6_performance_harness.py`
- `tests/test_phase8_promotion_targets.py`
- `docs/review/conformance/promotion_gate.target.json`

### Exit criteria

- the evaluator fails for every intentionally incomplete fixture
- the evaluator only passes when the actual strict target is met in full

## Phase 9I — release assembly and certifiable checkpoint

### Objective

Assemble the first promotable release root that satisfies the authoritative boundary, the strict target boundary, the flag target, the operator target, the performance target, and documentation integrity all at once.

### Work items

1. Create `docs/review/conformance/releases/0.3.9/release-0.3.9/`.
2. Promote all new independent scenario artifacts into that root.
3. Promote the final flag/operator/performance bundles into that root.
4. Update machine-readable current-state snapshots.
5. Update top-level docs so they truthfully say the strict target is now green.
6. Run the full validation set:
   - `evaluate_release_gates('.')`
   - `evaluate_release_gates(... strict boundary ...)`
   - `evaluate_promotion_target('.')`
   - targeted pytest suites
   - `python -m compileall -q src benchmarks tools`
7. Only after all gates pass, update the package version and release notes.

### Exit criteria

- authoritative boundary passes
- strict boundary passes
- flag surface passes
- operator surface passes
- performance target passes
- documentation / claim consistency passes
- composite promotion gate passes
- the repo can truthfully state that the package is certifiably fully featured and certifiably fully RFC compliant under the strict promotion target

## Parallelization map

### Stream A — strict RFC evidence

- Phase 9B foundation
- Phase 9C RFC 7692
- Phase 9D RFC 9110 bounded semantics
- Phase 9E RFC 6960

### Stream B — runtime / flag closure

- Phase 9A contract freeze
- Phase 9F TLS, observability, scheduler, keepalive closures

### Stream C — performance and release gates

- Phase 9A contract freeze
- Phase 9G performance closure
- Phase 9H evaluator hardening

### Critical path

`9A -> 9B -> (9C + 9D + 9E) -> 9F -> 9G -> 9H -> 9I`

Where practical, `9F` can begin in parallel with `9C`/`9D`/`9E`, but `9I` cannot start until all three streams are green.

## Definition of done for the full program

The package is promotion-ready only when all of the following are true:

1. All 13 missing strict-target scenarios exist in `external_matrix.release.json` and point to preserved passing artifacts under the new release root.
2. RFC 7692, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8, and RFC 6960 all resolve at `independent_certification`.
3. The 7 remaining public flags are fully wired, tested, and documented.
4. The operator surface remains green throughout the work.
5. The performance target emits all required metrics, thresholds, regression budgets, lanes, and artifact files.
6. The promotion evaluator enforces the full target contract without under-checking.
7. The new release root is assembled without mutating the frozen 0.3.7 candidate root.
8. Documentation remains truthful before, during, and after promotion.

## Phase 10 — optional post-promotion boundary expansion

This phase is **not** required for the current promotion target, but it is the correct next expansion once the strict target is closed.

### Recommended next RFC additions

1. RFC 7232 — conditional requests and validator semantics
2. RFC 9530 — `Content-Digest` / `Repr-Digest`

### Conditional later expansions

- RFC 9111 if the package intentionally becomes a cache / revalidation / static-asset product
- RFC 9421 if the package intentionally becomes an edge / gateway signing product

### Keep outside the transport-server core unless the product boundary expands

- JOSE (`RFC 7515`, `RFC 7516`, `RFC 7519`)
- COSE (`RFC 8152`, `RFC 9052`)

## Honest summary

The shortest route to a certifiably fully featured, certifiably fully RFC compliant package is **not** to widen the RFC boundary first.

The shortest honest route is:

1. close the 13 missing strict-target third-party artifacts
2. close the 7 remaining public runtime flags
3. close the strict performance target and evaluator
4. assemble a new promotable release root
5. only then expand into broader HTTP validator / digest work
