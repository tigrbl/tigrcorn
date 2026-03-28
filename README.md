# tigrcorn

`tigrcorn` is an ASGI3-compatible transport server implemented with package-owned protocol/runtime code.

```python
async def app(scope, receive, send):
    ...
```

## Installation

Base install:

```bash
python -m pip install -e .
```

Certification / repository-development install:

```bash
python -m pip install -e ".[certification,dev]"
```

Optional public feature surfaces are now declared explicitly in `pyproject.toml`:

```bash
python -m pip install -e ".[config-yaml]"      # YAML config files
python -m pip install -e ".[compression]"      # Brotli content coding / .br sidecars
python -m pip install -e ".[runtime-uvloop]"   # uvloop runtime selection
python -m pip install -e ".[full-featured]"    # current public optional feature bundle
```

An additional reserved extra is also declared:

```bash
python -m pip install -e ".[runtime-trio]"
```

`runtime-trio` is provided only as an explicit dependency path for future/internal work. This checkpoint does **not** advertise `--runtime trio` as a supported public runtime.

## Package boundary and non-goals

The current public package boundary is intentionally frozen as a **T/P/A/D/R** boundary and is governed by:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md` — authoritative in-bounds statement
- `docs/review/conformance/certification_boundary.json` — authoritative machine-readable RFC evidence policy
- `docs/review/conformance/BOUNDARY_NON_GOALS.md` — authoritative out-of-bounds statement
- `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md` — post-promotion in-bounds backlog

Boundary classes:

- **T — transport**
- **P — protocol**
- **A — application hosting**
- **D — delivery/origin behavior**
- **R — runtime/operator**

The current supported public runtime surface is **`auto`, `asyncio`, and `uvloop`**. The reserved `runtime-trio` extra does **not** widen that runtime contract.

Current explicit non-goals include Trio runtime, RFC 9218, RFC 9111, RFC 9530, RFC 9421, JOSE/COSE, parser/backend selection, WebSocket engine selection, and alternate app-interface pluggability. See `docs/review/conformance/BOUNDARY_NON_GOALS.md` for the full governing statement.

## Implemented surfaces in this archive

- HTTP/1.1 server path with streaming request bodies
- HTTP/1.1, HTTP/2, and HTTP/3 CONNECT relay tunneling
- trailer-field exposure on the HTTP/1.1, HTTP/2, and HTTP/3 request paths through an extension event
- HTTP content-coding negotiation for buffered responses (`gzip`, `deflate`, and `br` when Brotli support is present through `.[compression]`)
- WebSocket upgrade and frame processing over HTTP/1.1
- WebSocket permessage-deflate on the HTTP/1.1, HTTP/2, and HTTP/3 paths
- HTTP/2 codec, HPACK dynamic state, RFC 8441 WebSocket bootstrap, server push, and prior-knowledge server path
- RFC 9220 WebSocket bootstrap on the HTTP/3 carrier
- QUIC transport helpers, QUIC-TLS handshake support, session tickets, Retry, resumption, 0-RTT, migration handling, and HTTP/3 over UDP through the public API and CLI
- public mTLS-style client-certificate configuration for TLS and QUIC-TLS listeners through `ssl_ca_certs` and `ssl_require_client_cert`
- encrypted private-key PEM loading through `ssl_keyfile_password` and direct local CRL material loading through `ssl_crl`
- QPACK encoder/decoder streams and dynamic state
- certificate path validation, OCSP, CRL, and ALPN helpers in the package security subsystem
- package-owned TLS 1.3 server path on TCP/Unix listeners with record protection, ALPN selection, X.509 path validation, OCSP/CRL policy hooks, mTLS, and ASGI `tls` scope exposure
- TCP, Unix, UDP, pipe, and in-process listener implementations
- raw framed custom transport hosting path

## Canonical certification boundary

The package-wide certification target is defined by the canonical policy chain:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

The in-bounds boundary names the required RFC surface for RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 7541, RFC 9204, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 8446, RFC 9110 CONNECT semantics, RFC 9110 trailer fields, RFC 9110 content coding, RFC 7232, RFC 7233, RFC 8297, RFC 7838 §3 (Alt-Svc header-field advertisement), RFC 5280, RFC 6960, and RFC 7301.

The current public claim remains anchored to that canonical T/P/A/D/R boundary. The preserved stricter target in `docs/review/conformance/STRICT_PROFILE_TARGET.md` is green, but it is a stricter satisfied profile rather than a competing current package boundary.

For a focused audit of RFC 7232, RFC 7233, RFC 9111, RFC 9530, RFC 9421, JOSE, COSE, and related HTTP integrity / caching / signature features, see `docs/review/conformance/HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md`.

For a focused applicability / prioritization review of that RFC table plus a current competitor comparison against Uvicorn, Hypercorn, Daphne, and Granian, see `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`.
For a broader applicability / roadmap / competitor-positioning note covering that same RFC family, see `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md`.
For the exact Early Hints / Alt-Svc boundary decision, see `docs/review/conformance/PHASE4_RFC_BOUNDARY_FORMALIZATION.md`.

## Evidence tiers shipped with this archive

This archive separates three evidence tiers and binds them to a single current canonical release root:

1. **Local conformance** — `docs/review/conformance/corpus.json`
2. **Same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json`
3. **Independent certification** — `docs/review/conformance/external_matrix.release.json`

The current canonical release root is `docs/review/conformance/releases/0.3.9/release-0.3.9/`.

Historical preserved roots remain in-tree for provenance:

- `docs/review/conformance/releases/0.3.8/release-0.3.8/`
- `docs/review/conformance/releases/0.3.2/release-0.3.2/`
- `docs/review/conformance/releases/0.3.6/release-0.3.6/`
- `docs/review/conformance/releases/0.3.6-current/release-0.3.6-current/`
- `docs/review/conformance/releases/0.3.6-rfc-hardening/release-0.3.6-rfc-hardening/`
- `docs/review/conformance/releases/0.3.7/release-0.3.7/`

The canonical 0.3.9 root contains the full promoted bundle set plus the preserved auxiliary bundles:

- `tigrcorn-independent-certification-release-matrix/`
- `tigrcorn-same-stack-replay-matrix/`
- `tigrcorn-mixed-compatibility-release-matrix/`
- `tigrcorn-flag-surface-certification-bundle/`
- `tigrcorn-operator-surface-certification-bundle/`
- `tigrcorn-performance-certification-bundle/`
- `tigrcorn-certification-environment-bundle/`
- `tigrcorn-aioquic-adapter-preflight-bundle/`
- `tigrcorn-strict-validation-bundle/`
- the preserved local negative / behavior / validation bundles produced during Phases 9C–9E

The compatibility file `docs/review/conformance/external_matrix.current_release.json` remains a **mixed** matrix because it combines third-party HTTP/1.1 / HTTP/2 peers with same-stack HTTP/3 and RFC 9220 replay fixtures.

## Interoperability evidence status in this archive

The canonical independent matrix now includes preserved passing artifacts for:

- HTTP/1.1, HTTP/2, HTTP/2 over TLS, WebSocket over HTTP/1.1, WebSocket over HTTP/2, and QUIC handshake interoperability
- third-party `aioquic` HTTP/3 request/response, mTLS, Retry, resumption, 0-RTT, migration, and GOAWAY / QPACK scenarios
- third-party `aioquic` RFC 9220 WebSocket-over-HTTP/3 scenarios

The package-owned TCP/TLS listener path is backed by package-owned TLS 1.3, ALPN, X.509 validation, revocation policy hooks, and mTLS integration.

As a result, the canonical release gates now pass and the package is **certifiably fully RFC compliant under the authoritative certification boundary** in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

Important scope note:

- Under the current authoritative boundary, RFC 7692, RFC 9110 CONNECT / trailers / content coding, RFC 7232, RFC 7233, RFC 8297, RFC 7838 §3, and RFC 6960 are intentionally satisfied at `local_conformance` rather than `independent_certification`.
- Those surfaces are still part of the required RFC surface, and they are satisfied at the tier required by the authoritative boundary.
- The stricter all-surfaces-independent target is now also satisfied and is documented in `docs/review/conformance/STRICT_PROFILE_TARGET.md`.
- The provisional all-surfaces and flow-control bundles remain in-tree as historical planning / review aids and do not change the canonical release-gate result.

For the point-in-time repository summary, use `CURRENT_REPOSITORY_STATE.md` together with `docs/review/conformance/current_state_chain.current.json`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. For an explicit gap analysis of the current Phase 9I checkpoint, see `docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md` and `docs/review/conformance/package_compliance_review_phase9i.current.json`. For the machine-readable certification policy, see `docs/review/conformance/certification_boundary.json`. For the offline remediation attempt that produced the provisional bundles, see `docs/review/conformance/OFFLINE_COMPLETION_ATTEMPT.md`, `docs/review/conformance/offline_completion_state.json`, `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`, `docs/review/conformance/all_surfaces_independent_state.json`, `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md`, `docs/review/conformance/SECONDARY_PARTIALS_STATUS.md`, and `docs/review/conformance/secondary_partials_state.json`. Historical execution-plan and phase-closure records remain in-tree for provenance, including `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md` / `docs/review/conformance/phase9_implementation_plan.current.json`, `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md` / `docs/review/conformance/phase9a_promotion_contract.current.json`, and `docs/review/conformance/PHASE9B_INDEPENDENT_HARNESS_FOUNDATION.md` / `docs/review/conformance/phase9b_independent_harness.current.json`. Those retained phase records are not the canonical package-wide current-state chain. The direct third-party aioquic adapter preflight now also lives in `docs/review/conformance/AIOQUIC_ADAPTER_PREFLIGHT.md` and `docs/review/conformance/aioquic_adapter_preflight.current.json`.

## Running

```bash
python -m tigrcorn examples.echo_http.app:app
```

UDP / HTTP/3 example with QUIC-TLS certificates:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem
```

UDP / HTTP/3 example with client-certificate verification enabled:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem --ssl-ca-certs client-ca.pem --ssl-require-client-cert
```

UDP / HTTP/3 example with Retry enabled:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem --quic-require-retry
```

## Config and CLI substrate

## Public lifecycle and embedding contract

The public lifecycle-hook and embedding contract is now documented in `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`.

That document freezes:

- `on_startup`, `on_shutdown`, and `on_reload` hook signatures
- ordering relative to `lifespan.startup()` and `lifespan.shutdown()`
- startup / shutdown / reload failure semantics
- the public `EmbeddedServer` contract, including idempotent `start()`, no-op `close()` before startup, and bound-endpoint inspection

The package-owned TLS / revocation material surface now also includes `--ssl-keyfile-password` and `--ssl-crl` with matching config/env/docs/test coverage.

This checkpoint adds a nested configuration model and grouped CLI families for:

- app / process / development
- listener / binding
- TLS / security
- logging / observability
- resource / timeout / concurrency
- protocol / transport

Config precedence is now documented as:

`CLI > env > config file > defaults`

See:

- `docs/review/conformance/CLI_FLAG_SURFACE.md`
- `docs/review/conformance/cli_flag_surface.json`
- `docs/review/conformance/DEPLOYMENT_PROFILES.md`
- `docs/review/conformance/deployment_profiles.json`
- `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md`


## Phase 3 strict RFC checkpoint

This checkpoint adds a first-class public policy surface for the stricter RFC gap set:

```bash
python -m tigrcorn examples.echo_http.app:app \
  --websocket-compression permessage-deflate \
  --connect-policy allowlist \
  --connect-allow 127.0.0.1:443 \
  --trailer-policy strict \
  --content-coding-policy allowlist \
  --content-codings gzip,deflate \
  --ssl-alpn h2,http/1.1 \
  --ssl-ocsp-mode require \
  --ssl-ocsp-cache-size 128 \
  --ssl-ocsp-max-age 43200 \
  --ssl-crl-mode off \
  --ssl-revocation-fetch off
```

Important qualification:

- this checkpoint lands the **public RFC-scoped flags and runtime wiring**
- it does **not** by itself make the stricter all-surfaces-independent overlay green
- the current authoritative canonical boundary remains the source of truth for the package's release-green status


## Phase 4 operator surface

This checkpoint adds a real operator surface on top of the earlier protocol / RFC work. The package now has:

- process-worker supervision
- stdlib polling reload
- trusted proxy normalization and `root_path` propagation
- structured/file logging
- a Prometheus-style metrics endpoint
- public runtime wiring for timeout, limit, and quota controls

Examples:

```bash
python -m tigrcorn examples.echo_http.app:app \
  --workers 2 \
  --pid /tmp/tigrcorn.pid \
  --access-log-file /tmp/tigrcorn-access.log \
  --metrics --metrics-bind 127.0.0.1:9001
```

```bash
python -m tigrcorn examples.echo_http.app:app \
  --reload \
  --reload-dir src \
  --proxy-headers \
  --forwarded-allow-ips 127.0.0.1 \
  --root-path /svc
```


## Phase 5 evidence promotion

The repository now preserves a minimum independent QUIC / HTTP3 flow-control bundle and a minimum certified intermediary / proxy-adjacent corpus in addition to the earlier provisional / seed roots retained for provenance.

## Phase 6 performance closure

This checkpoint adds a package-local performance certification surface separate from the canonical RFC boundary.

The repository now ships:

- `src/tigrcorn/compat/perf_runner.py`
- `tools/run_perf_matrix.py`
- `benchmarks/` drivers and profile catalog
- `docs/review/performance/PERFORMANCE_BOUNDARY.md`
- `docs/review/performance/performance_matrix.json`
- preserved baseline and current-release artifact roots under `docs/review/performance/artifacts/`

The current Phase 6 matrix preserves **32 required profiles** spanning HTTP, WebSocket, TLS / PKI, semantic extras, and operator overhead. Each profile is tied to a deployment profile from `docs/review/conformance/deployment_profiles.json`, and every RFC-scoped profile also preserves correctness-under-load evidence.

Important qualification:

- this is a **release-certified product-performance claim surface**
- it is **not** an RFC claim
- it does **not** by itself close the stricter all-surfaces-independent RFC overlay

## Phase 9B independent harness foundation

This checkpoint adds the reusable independent-certification harness foundation needed for the remaining strict-target third-party scenarios.

The repository now ships:

- `tools/interop_wrappers.py`
- `docs/review/conformance/interop_wrapper_registry.current.json`
- `docs/review/conformance/INTEROP_HARNESS_ARTIFACT_SCHEMA.md`
- a proof bundle under `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-harness-foundation-bundle/`

Important qualification:

- this checkpoint proves the reusable wrapper / artifact / validation substrate
- it does **not** close the remaining 13 strict-target independent scenarios
- it does **not** by itself make the package certifiably fully featured under the stricter promotion target



## Phase 9C RFC 7692 independent closure

The executed Phase 9C RFC 7692 closure is now documented through:

- `docs/review/conformance/PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md`
- `docs/review/conformance/phase9c_rfc7692_independent_closure.current.json`
- `DELIVERY_NOTES_PHASE9C_RFC7692_INDEPENDENT_CLOSURE.md`

## Phase 9D1 CONNECT relay independent closure

The executed Phase 9D1 CONNECT relay checkpoint is now documented through:

- `docs/review/conformance/PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md`
- `docs/review/conformance/phase9d1_connect_relay_independent.current.json`
- `DELIVERY_NOTES_PHASE9D1_CONNECT_RELAY_INDEPENDENT_CLOSURE.md`

Current truth for that checkpoint:

- HTTP/1.1 CONNECT relay preserved third-party artifact: **passed**
- HTTP/2 CONNECT relay preserved third-party artifact: **passed**
- HTTP/3 CONNECT relay preserved third-party artifact: **passed**
- strict target: **still not yet complete**


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

- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- `DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`


## Certification environment freeze

The strict-promotion release workflow now freezes the certification environment before it invokes any Phase 9 checkpoint script.

Current artifacts for that contract live in:

- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`
- `DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md`

## aioquic adapter preflight

The strict-promotion workflow now also preserves a direct third-party `aioquic` adapter preflight before any Phase 9 checkpoint script is allowed to run.

Current artifacts for that proof live in:

- `docs/review/conformance/AIOQUIC_ADAPTER_PREFLIGHT.md`
- `docs/review/conformance/aioquic_adapter_preflight.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-aioquic-adapter-preflight-bundle/`
- `DELIVERY_NOTES_AIOQUIC_ADAPTER_PREFLIGHT.md`

The release workflow path is `.github/workflows/phase9-certification-release.yml`, and the local wrapper is `tools/run_phase9_release_workflow.py`.
