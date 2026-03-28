# Conformance and external interoperability evidence

The canonical package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Canonical policy sources

The current package policy chain is:

- `CERTIFICATION_BOUNDARY.md` — authoritative in-bounds statement
- `certification_boundary.json` — authoritative machine-readable RFC evidence policy
- `BOUNDARY_NON_GOALS.md` — authoritative out-of-bounds statement
- `NEXT_DEVELOPMENT_TARGETS.md` — current in-bounds post-promotion backlog

The preserved stricter profile in `STRICT_PROFILE_TARGET.md` remains green, but it is a satisfied stricter profile rather than a competing current package boundary.

## Current canonical release root

The current release evidence is consolidated under `docs/review/conformance/releases/0.3.9/release-0.3.9/`.

That canonical 0.3.9 release root contains the assembled strict-promotion bundle set plus the preserved auxiliary bundles:

- `tigrcorn-independent-certification-release-matrix/`
- `tigrcorn-same-stack-replay-matrix/`
- `tigrcorn-mixed-compatibility-release-matrix/`
- `tigrcorn-flag-surface-certification-bundle/`
- `tigrcorn-operator-surface-certification-bundle/`
- `tigrcorn-performance-certification-bundle/`
- `tigrcorn-rfc7692-local-negative-artifacts/`
- `tigrcorn-connect-relay-local-negative-artifacts/`
- `tigrcorn-trailer-fields-local-behavior-artifacts/`
- `tigrcorn-content-coding-local-behavior-artifacts/`
- `tigrcorn-ocsp-local-validation-artifacts/`
- `tigrcorn-certification-environment-bundle/`
- `tigrcorn-aioquic-adapter-preflight-bundle/`
- `tigrcorn-strict-validation-bundle/`

The older `0.3.2`, `0.3.6`, `0.3.6-rfc-hardening`, `0.3.6-current`, and the frozen `0.3.7` candidate root remain preserved for provenance, but they are not the canonical current release root.

## 1. Local conformance corpus

`corpus.json` maps RFC-oriented behavior to local fixtures and unit tests.

## 2. Same-stack replay evidence

`external_matrix.same_stack_replay.json` isolates replayable scenarios that still use tigrcorn-owned peers such as `tigrcorn-public-client`.

Those scenarios are useful regression evidence. They are not independent certification evidence.

## 3. Independent certification evidence

`external_matrix.release.json` is the canonical independent certification matrix.

That matrix now includes preserved passing artifacts for:

- HTTP/1.1
- HTTP/2
- HTTP/2 over TLS
- WebSocket over HTTP/1.1
- RFC 8441 WebSocket over HTTP/2
- OpenSSL QUIC handshake interoperability
- third-party `aioquic` HTTP/3 request/response and QUIC feature-axis scenarios
- third-party `aioquic` RFC 9220 WebSocket-over-HTTP/3 scenarios

## Current authoritative status

The package is now **certifiably fully RFC compliant under the authoritative certification boundary**.

The canonical 0.3.9 release root is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

The remaining broader items are explicitly outside the current authoritative blocker set:

- RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 remain intentionally bounded at `local_conformance` in the current authoritative machine-readable policy
- the stricter all-surfaces-independent overlay for those surfaces now also passes
- the provisional all-surfaces and flow-control bundles remain non-certifying historical review aids
- the historical intermediary / proxy seed corpus improves repository completeness and remains preserved
- a minimum certified intermediary / proxy-adjacent corpus now exists under `intermediary_proxy_corpus_minimum_certified/`, but it is still intentionally narrower than a full multi-hop intermediary certification program

For the explicit policy decision that resolved the earlier documentation mismatch, see `docs/review/conformance/CERTIFICATION_POLICY_ALIGNMENT.md`.

For historical offline remediation artifacts and strict-profile planning material, see `docs/review/conformance/OFFLINE_COMPLETION_ATTEMPT.md`, `docs/review/conformance/offline_completion_state.json`, `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`, `docs/review/conformance/all_surfaces_independent_state.json`, `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md`, `docs/review/conformance/SECONDARY_PARTIALS_STATUS.md`, and `docs/review/conformance/secondary_partials_state.json`.

## Canonical current-state chain

The canonical package-wide current-state chain is now explicitly defined in:

- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`
- `CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/phase9i_strict_validation.current.json`

Historical phase checkpoint snapshots still keep stable `*.current.json` file names where needed for tests and provenance, but they are now explicitly labeled by `document_role` and are not ambiguous current-state sources.

## Scoped current audits and archival compatibility docs

The focused HTTP integrity/caching/signatures audit and the RFC applicability / competitor comparison documents remain current for their own scopes, but they are **not** the canonical package-wide current-state source. Use `docs/review/conformance/current_state_chain.current.json` to distinguish canonical package truth from scoped audits and historical snapshots.

The canonical current integrated Phase 4 example tree is `examples/advanced_delivery/`. The older `examples/advanced_protocol_delivery/` path is retained as an archival compatibility path for the original Phase 4 checkpoint examples.

## Config / CLI substrate tracking

The Phase 2 config / CLI surface is documented in:

- `CLI_FLAG_SURFACE.md`
- `cli_flag_surface.json`
- `OPTIONAL_DEPENDENCY_SURFACE.md`
- `optional_dependency_surface.current.json`
- `DEPLOYMENT_PROFILES.md`
- `deployment_profiles.json`
- `NEXT_DEVELOPMENT_TARGETS.md`


## Operator-surface tracking

The current operator-surface checkpoint is documented in:

- `PHASE4_OPERATOR_SURFACE_STATUS.md`
- `phase4_operator_surface_status.current.json`

The current public lifecycle / embedder contract is documented in:

- `../../LIFECYCLE_AND_EMBEDDED_SERVER.md`
- `phase5_phase6_phase7_tls_lifecycle_flag_truth.current.json`

Those documents track the public production operator surface separately from the canonical RFC boundary so the package can remain honest about what is RFC-certified versus what is operationally implemented and tested.


## Phase 5 reference matrices

Additional Phase 5 reference matrices now live in:

- `external_matrix.flow_control.minimum.json`
- `external_matrix.intermediary_proxy.minimum.json`

## Performance-boundary tracking

Phase 6 adds a package-local performance certification surface under `docs/review/performance/`.

Relevant files are:

- `../performance/PERFORMANCE_BOUNDARY.md`
- `../performance/performance_matrix.json`
- `../performance/artifacts/README.md`
- `PHASE6_PERFORMANCE_STATUS.md`
- `phase6_performance_status.current.json`

That surface is intentionally separate from the canonical RFC boundary. It proves reproducible same-stack throughput / latency / overhead behavior with correctness-under-load checks, but it is not a substitute for RFC evidence tiers.


## Focused HTTP integrity / caching / signatures audit

A focused audit for RFC 7232, RFC 9111, RFC 9530, RFC 9421, JOSE, COSE, and related feature-level questions now lives in:

- `HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md`
- `http_integrity_caching_signatures_status.current.json`

That audit explains why the package remains honest under its transport-centric certification boundary, now including RFC 7232 / RFC 7233 direct entity semantics, RFC 8297 Early Hints, and the bounded RFC 7838 §3 Alt-Svc header-field surface, while still not claiming the broader HTTP caching / digest / signature stack.

A companion applicability / prioritization and competitor comparison now lives in:

- `RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- `rfc_applicability_and_competitor_status.current.json`

That companion classifies the broader RFC table into core current-boundary work, adjacent optional next-step work, conditional boundary-expansion work, and non-core product-layer work, while also preserving a current documented comparison against Uvicorn, Hypercorn, Daphne, and Granian.

A companion applicability / roadmap / competitor snapshot now lives in:

- `RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md`
- `rfc_applicability_and_competitor_support.current.json`
- `PHASE4_RFC_BOUNDARY_FORMALIZATION.md`
- `phase4_rfc_boundary_formalization_checkpoint.current.json`

## Preserved stricter profile and current development tracking

The preserved stricter profile remains documented through:

- `STRICT_PROFILE_TARGET.md`
- `certification_boundary.strict_target.json`
- `FLAG_CERTIFICATION_TARGET.md`
- `flag_contracts.json`
- `flag_covering_array.json`
- `../performance/PERFORMANCE_SLOS.md`
- `../performance/performance_slos.json`
- `promotion_gate.target.json`

Those files remain useful for promotion/audit provenance, but they do **not** redefine the current package boundary.

The current **in-bounds** post-promotion backlog is now documented through:

- `NEXT_DEVELOPMENT_TARGETS.md`
- `BOUNDARY_NON_GOALS.md`

That pair defines what the repository is still choosing to build next, and what it is explicitly **not** choosing to build, inside the current T/P/A/D/R governance model.

A repository-level package compliance review for the assembled Phase 9I checkpoint now also lives in:

- `PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md`
- `package_compliance_review_phase9i.current.json`

The historical strict-target snapshot for this target remains preserved in `PHASE8_STRICT_PROMOTION_TARGET_STATUS.md` and `phase8_strict_promotion_target_status.current.json`. Those files are retained for provenance and are not the canonical package-wide current-state chain.

A detailed execution plan for closing the remaining work now also lives in:

- `PHASE9_IMPLEMENTATION_PLAN.md`
- `phase9_implementation_plan.current.json`

The executed Phase 9A contract freeze is now documented through:

- `PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `PHASE9A_EXECUTION_BACKLOG.md`
- `phase9a_promotion_contract.current.json`
- `phase9a_execution_backlog.current.json`

The executed Phase 9B independent-harness foundation is now documented through:

- `PHASE9B_INDEPENDENT_HARNESS_FOUNDATION.md`
- `INTEROP_HARNESS_ARTIFACT_SCHEMA.md`
- `interop_wrapper_registry.current.json`
- `phase9b_independent_harness.current.json`

Those executed phase records remain in-tree for provenance and stable references. Their `*.current.json` file names do not make them the canonical package-wide current-state chain.


## Phase 9C RFC 7692 independent closure

The executed Phase 9C RFC 7692 closure is now documented through:

- `docs/review/conformance/PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md`
- `docs/review/conformance/phase9c_rfc7692_independent_closure.current.json`
- `DELIVERY_NOTES_PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md`

## Phase 9D1 CONNECT relay independent closure

The executed Phase 9D1 CONNECT relay closure is now documented through:

- `PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md`
- `phase9d1_connect_relay_independent.current.json`
- `../releases/0.3.9/release-0.3.9/tigrcorn-connect-relay-local-negative-artifacts/`
- `DELIVERY_NOTES_PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md`



## Phase 9D2 trailer fields independent closure

The executed Phase 9D2 trailer-fields closure is now documented through:

- `docs/review/conformance/PHASE9D2_TRAILER_FIELDS_INDEPENDENT_CLOSURE.md`
- `docs/review/conformance/phase9d2_trailer_fields_independent.current.json`
- `docs/review/conformance/TRAILER_FIELDS_LOCAL_BEHAVIOR_ARTIFACTS.md`
- `docs/review/conformance/trailer_fields_local_behavior_artifacts.current.json`
- `DELIVERY_NOTES_PHASE9D2_TRAILER_FIELDS_INDEPENDENT_CLOSURE.md`


## Phase 9D3 content-coding independent closure

The executed Phase 9D3 content-coding closure is now documented through:

- `docs/review/conformance/PHASE9D3_CONTENT_CODING_INDEPENDENT_CLOSURE.md`
- `docs/review/conformance/phase9d3_content_coding_independent.current.json`
- `docs/review/conformance/CONTENT_CODING_LOCAL_BEHAVIOR_ARTIFACTS.md`
- `docs/review/conformance/content_coding_local_behavior_artifacts.current.json`
- `DELIVERY_NOTES_PHASE9D3_CONTENT_CODING_INDEPENDENT_CLOSURE.md`


## Phase 9E OCSP independent closure

The executed Phase 9E OCSP closure is now documented through:

- `docs/review/conformance/PHASE9E_OCSP_INDEPENDENT_CLOSURE.md`
- `docs/review/conformance/phase9e_ocsp_independent.current.json`
- `docs/review/conformance/OCSP_LOCAL_VALIDATION_ARTIFACTS.md`
- `docs/review/conformance/ocsp_local_validation_artifacts.current.json`
- `DELIVERY_NOTES_PHASE9E_OCSP_INDEPENDENT_CLOSURE.md`


## Phase 9F1 TLS cipher-policy closure

The executed Phase 9F1 TLS cipher-policy closure is now documented through:

- `docs/review/conformance/PHASE9F1_TLS_CIPHER_POLICY_CLOSURE.md`
- `docs/review/conformance/phase9f1_tls_cipher_policy.current.json`
- `DELIVERY_NOTES_PHASE9F1_TLS_CIPHER_POLICY_CLOSURE.md`


## Phase 9F2 logging and exporter closure

The executed Phase 9F2 observability closure is now documented through:

- `docs/review/conformance/PHASE9F2_LOGGING_EXPORTER_CLOSURE.md`
- `docs/review/conformance/phase9f2_logging_exporter.current.json`
- `DELIVERY_NOTES_PHASE9F2_LOGGING_EXPORTER_CLOSURE.md`


## Phase 9F3 concurrency and WebSocket keepalive closure

The executed Phase 9F3 concurrency / keepalive closure is now documented through:

- `docs/review/conformance/PHASE9F3_CONCURRENCY_WEBSOCKET_KEEPALIVE_CLOSURE.md`
- `docs/review/conformance/phase9f3_concurrency_keepalive.current.json`
- `DELIVERY_NOTES_PHASE9F3_CONCURRENCY_WEBSOCKET_KEEPALIVE_CLOSURE.md`


## Phase 9G strict performance closure

The executed Phase 9G strict-performance closure is now documented through:

- `docs/review/conformance/PHASE9G_STRICT_PERFORMANCE_CLOSURE.md`
- `docs/review/conformance/phase9g_strict_performance.current.json`
- `DELIVERY_NOTES_PHASE9G_STRICT_PERFORMANCE_CLOSURE.md`


## Phase 9H promotion-evaluator hardening

The executed Phase 9H evaluator-hardening checkpoint is now documented through:

- `docs/review/conformance/PHASE9H_PROMOTION_EVALUATOR_HARDENING.md`
- `docs/review/conformance/phase9h_promotion_evaluator.current.json`
- `DELIVERY_NOTES_PHASE9H_PROMOTION_EVALUATOR_HARDENING.md`


## Phase 9I release assembly and certifiable checkpoint

The executed Phase 9I release-assembly checkpoint is now documented through:

- `PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `phase9i_release_assembly.current.json`
- `../releases/0.3.9/release-0.3.9/`
- `../../DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`


## Certification environment freeze

The strict-promotion release workflow now freezes the certification environment before it invokes any Phase 9 checkpoint script.

Current artifacts for that contract live in:

- `CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `certification_environment_freeze.current.json`
- `releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`
- `../../DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md`

## aioquic adapter preflight

The direct third-party `aioquic` adapter preflight now also lives in:

- `AIOQUIC_ADAPTER_PREFLIGHT.md`
- `aioquic_adapter_preflight.current.json`
- `releases/0.3.9/release-0.3.9/tigrcorn-aioquic-adapter-preflight-bundle/`
- `../../DELIVERY_NOTES_AIOQUIC_ADAPTER_PREFLIGHT.md`

## Phase 9I strict validation

- `PHASE9I_STRICT_VALIDATION.md`
- `phase9i_strict_validation.current.json`
