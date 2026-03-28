# tigrcorn

[![repo line](https://img.shields.io/badge/repo_line-0.3.9-2f7ed8)](docs/review/conformance/releases/0.3.9/release-0.3.9/)
[![repo size](https://img.shields.io/badge/repo_size-24.25_MB-5c7cfa)](docs/gov/tree.md)
[![PyPI published](https://img.shields.io/pypi/v/tigrcorn?label=last%20pypi%20publish)](https://pypi.org/project/tigrcorn/)
[![PyPI downloads](https://img.shields.io/pepy/dt/tigrcorn?label=pypi%20downloads)](https://pypi.org/project/tigrcorn/)
[![authoritative boundary](https://img.shields.io/badge/authoritative_boundary-green)](docs/review/conformance/CERTIFICATION_BOUNDARY.md)
[![strict profile](https://img.shields.io/badge/strict_profile-green)](docs/review/conformance/STRICT_PROFILE_TARGET.md)
[![operator surface](https://img.shields.io/badge/operator_surface-green)](docs/review/conformance/PHASE4_OPERATOR_SURFACE_STATUS.md)
[![promotion](https://img.shields.io/badge/promotion-green)](docs/review/conformance/releases/0.3.9/release-0.3.9/)

`tigrcorn` is an ASGI3-compatible transport server implemented with package-owned transport, protocol, runtime, delivery, and security code. The repository target is the promoted `0.3.9` line, while external publication can lag repository promotion.

```python
async def app(scope, receive, send):
    ...
```

## Status at a glance

| Item | Current state |
|---|---|
| Repo line | `0.3.9` |
| Canonical release root | `docs/review/conformance/releases/0.3.9/release-0.3.9/` |
| Historical released root preserved | `docs/review/conformance/releases/0.3.8/release-0.3.8/` |
| Authoritative boundary | green |
| Strict profile | green |
| Promotion target | green |
| Current package claim | **certifiably fully RFC compliant under the authoritative certification boundary** |
| Current package claim under promoted root | **certifiably fully featured** |
| Canonical current-state entrypoint | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` |
| Mutable governance entrypoint | `docs/gov/README.md` |
| Agentic workflow entrypoint | `AGENTS.md` |

Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` for the point-in-time repository summary, and use `docs/review/conformance/current_state_chain.current.json` for the machine-readable current-state chain.

## Install

Base install:

```bash
python -m pip install -e .
```

Certification / repository-development install:

```bash
python -m pip install -e ".[certification,dev]"
```

Optional feature/dependency surfaces:

```bash
python -m pip install -e ".[config-yaml]"
python -m pip install -e ".[compression]"
python -m pip install -e ".[runtime-uvloop]"
python -m pip install -e ".[full-featured]"
```

Reserved extra:

```bash
python -m pip install -e ".[runtime-trio]"
```

`runtime-trio` is declared as a reserved dependency path only. Runtime `trio` is **not** part of the supported public runtime surface. See `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md`.

## Package boundary

The canonical policy chain is:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

The current package boundary is intentionally frozen as a **T/P/A/D/R** boundary:

- **T — transport**
- **P — protocol**
- **A — application hosting**
- **D — delivery/origin behavior**
- **R — runtime/operator**

The current supported public runtime surface is `auto`, `asyncio`, and `uvloop`.

Explicit non-goals include:

- Trio runtime
- RFC 9218 prioritization
- RFC 9111 caching/freshness
- RFC 9530 digest fields
- RFC 9421 HTTP signatures
- JOSE / COSE
- parser/backend pluggability
- WebSocket engine pluggability
- alternate interface families such as ASGI2 / WSGI / RSGI

Use `docs/review/conformance/BOUNDARY_NON_GOALS.md` as the authoritative out-of-bounds statement.

## Evidence tiers and promoted release roots

This archive separates three evidence tiers and binds them to a single current canonical release root:

1. **Local conformance** — `docs/review/conformance/corpus.json`
2. **Same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json`
3. **Independent certification** — `docs/review/conformance/external_matrix.release.json`

The current canonical release root is `docs/review/conformance/releases/0.3.9/release-0.3.9/`.

Historical preserved roots remain in-tree for provenance:

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

## Support and certification legend

These status markers are used in the comparison matrices below.

| Marker | Meaning |
|---|---|
| `C-RFC` | tigrcorn implements the surface and includes it in the current certified RFC boundary |
| `C-OP` | tigrcorn implements the surface and includes it in the current certified public/operator surface |
| `S` | current official docs show first-class public support |
| `Cfg` | current official docs show public support through a primary config surface rather than a dedicated CLI switch |
| `P` | partial, optional, qualified, or draft support |
| `M` | middleware/wrapper based support instead of a first-class server surface |
| `O` | intentionally outside tigrcorn's current product boundary |
| `—` | no current official public support claim found in the reviewed primary docs |

Peer statuses below are documentation snapshots, not certification claims by this repository. The maintained companion sources for these tables live in `docs/comp/`.

## RFC target comparison

Reviewed against current official peer docs on `2026-03-28`.

| RFC target | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| RFC 9112 HTTP/1.1 | C-RFC | S | S | S | Core HTTP/1.1 server path. |
| RFC 9113 HTTP/2 | C-RFC | — | S | S | Hypercorn and Granian publicly document HTTP/2. |
| RFC 9114 HTTP/3 | C-RFC | — | P | — | Hypercorn documents a QUIC/HTTP/3 path via `--quic-bind`; Granian says HTTP/3 is future work. |
| RFC 9000 QUIC transport | C-RFC | — | P | — | Hypercorn's public QUIC surface is optional/qualified. |
| RFC 9001 QUIC-TLS | C-RFC | — | P | — | Hypercorn's public QUIC/TLS path is qualified by its optional HTTP/3 stack. |
| RFC 9002 QUIC recovery | C-RFC | — | P | — | Hypercorn's public docs do not independently certify recovery behavior. |
| RFC 7541 HPACK | C-RFC | — | P | P | Peer docs imply HPACK through HTTP/2 support but do not certify it separately. |
| RFC 9204 QPACK | C-RFC | — | P | — | Peer docs do not expose a package-owned QPACK claim comparable to tigrcorn. |
| RFC 6455 WebSocket | C-RFC | S | S | S | All three peers publicly document WebSocket support. |
| RFC 7692 permessage-deflate | C-RFC | S | — | — | Uvicorn exposes per-message-deflate; Hypercorn and Granian do not document it in the reviewed sources. |
| RFC 8441 WebSocket over HTTP/2 | C-RFC | — | S | — | Hypercorn publicly documents WebSockets over HTTP/2. |
| RFC 9220 WebSocket over HTTP/3 | C-RFC | — | — | — | Only tigrcorn currently ships and certifies this surface in the reviewed set. |
| RFC 8446 TLS 1.3 | C-RFC | P | P | P | Peer docs expose TLS controls but do not publish a comparable package-owned TLS 1.3 certification claim. |
| RFC 7301 ALPN | C-RFC | — | S | — | Hypercorn documents ALPN protocol control. |
| RFC 5280 X.509 validation | C-RFC | P | P | P | Peer docs expose CA/client-certificate settings but not tigrcorn-style package-owned certification. |
| RFC 6960 OCSP | C-RFC | — | — | — | No peer public OCSP surface was found in the reviewed docs. |
| RFC 9110 §9.3.6 CONNECT relay | C-RFC | — | — | — | tigrcorn-only surface in this comparison. |
| RFC 9110 §6.5 trailer fields | C-RFC | — | — | — | tigrcorn-only public surface in this comparison. |
| RFC 9110 §8 content coding | C-RFC | — | — | — | tigrcorn-only public content-coding policy surface in this comparison. |
| RFC 7232 conditional requests | C-RFC | — | — | — | tigrcorn-only boundary target in this comparison. |
| RFC 7233 range requests | C-RFC | — | — | — | tigrcorn-only boundary target in this comparison. |
| RFC 8297 Early Hints | C-RFC | — | — | — | tigrcorn-only boundary target in this comparison. |
| RFC 7838 §3 Alt-Svc header | C-RFC | — | Cfg | — | Hypercorn documents `alt_svc_headers` via config; tigrcorn ships CLI + certified bounded header surface. |

Companion source: `docs/comp/rfc.md`

## CLI feature comparison

Reviewed against current official peer docs on `2026-03-28`.

| CLI feature family | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| App factory loading | C-OP | S | — | S | Granian and Uvicorn expose `--factory`; Hypercorn expects an app object path. |
| Working-dir / app-dir control | C-OP | S | Cfg | S | Hypercorn exposes `application_path` via config. |
| Config file loading | C-OP | — | S | — | Hypercorn supports TOML/Python/module config. |
| Env-file loading | C-OP | S | — | S | Granian requires its dotenv extra for env files. |
| Env-prefix override | C-OP | — | — | — | tigrcorn-only public env-prefix surface. |
| Reload + watch filters | C-OP | S | P | S | Hypercorn documents reload; Granian documents reload paths/ignore controls. |
| Workers + recycling | C-OP | S | S | S | All four expose worker/process controls; exact semantics differ. |
| Runtime / worker-class selection | C-OP | P | S | S | Uvicorn exposes loop/http/ws selectors; Hypercorn exposes worker class; Granian exposes loop/runtime mode/task implementation. |
| Host / port bind | C-OP | S | S | S | Common across all four. |
| Unix domain socket bind | C-OP | S | S | S | Common across all four. |
| FD bind | C-OP | S | S | — | Granian docs do not expose an FD bind in the reviewed README. |
| Multi-bind / endpoint grammar | C-OP | — | S | P | Hypercorn documents multiple binds; Granian exposes route/mount pairs but not Hypercorn-style bind grammar. |
| QUIC / HTTP/3 bind | C-OP | — | S | — | Hypercorn exposes `--quic-bind`; Uvicorn and Granian do not in the reviewed docs. |
| Transport selection incl. pipe/inproc/raw | C-OP | — | — | — | tigrcorn-only surface. |
| Socket ownership / permissions | C-OP | — | S | S | Hypercorn exposes user/group/umask; Granian exposes UDS permissions and process controls. |
| Server-native static route / mount | C-OP | — | — | S | Granian and tigrcorn expose first-class static serving. |
| Static dir-to-file / index control | C-OP | — | — | S | Granian exposes `--static-path-dir-to-file`; tigrcorn also exposes explicit index policy controls. |
| Static expires control | C-OP | — | — | S | Granian and tigrcorn expose explicit static expiry controls. |
| TLS key / cert input | C-OP | S | S | S | All four expose basic TLS material input. |
| Encrypted key password | C-OP | S | S | S | All peers now document password-protected key support. |
| CA / client-cert verification | C-OP | S | S | S | All peers expose a public client-cert verification path. |
| Direct CRL file input | C-OP | — | — | S | tigrcorn and Granian expose direct CRL material input in the reviewed docs. |
| OCSP controls | C-OP | — | — | — | tigrcorn-only public OCSP mode/cache/soft-fail surface in this comparison. |
| ALPN controls | C-OP | — | Cfg | — | Hypercorn documents ALPN via config; tigrcorn exposes a CLI surface. |
| Proxy trust controls | C-OP | S | M | M | Hypercorn points to ProxyFixMiddleware; Granian points to proxy wrappers. |
| Custom server/date/header controls | C-OP | S | Cfg | P | Hypercorn exposes server/date behavior via config; Granian has url-path-prefix and process/log options but not the same header family. |
| Structured log / log files | C-OP | P | S | S | Uvicorn supports log config; Hypercorn and Granian expose richer file-oriented logging surfaces. |
| Metrics / StatsD / OTel | C-OP | — | S | S | Hypercorn documents StatsD; Granian documents Prometheus metrics. |
| Timeouts / concurrency limits | C-OP | S | S | S | All four expose operator-grade timeout and limit controls. |
| HTTP/1 tuning family | C-OP | P | Cfg | S | Uvicorn documents only h11 incomplete-event size; Hypercorn exposes h11 sizing in config; Granian exposes a broader H1 family. |
| HTTP/2 tuning family | C-OP | — | Cfg | S | Hypercorn exposes H2 sizing in config; Granian exposes a larger direct CLI family. |
| WebSocket size / queue / ping / compression | C-OP | S | P | P | Hypercorn documents size and ping interval; Granian documents WebSocket support but not the same full CLI family in the reviewed excerpt. |
| Alt-Svc controls | C-OP | — | Cfg | — | Hypercorn exposes config-based Alt-Svc headers. |
| CONNECT / trailer / content-coding policy | C-OP | — | — | — | tigrcorn-only policy family in this comparison. |

Companion source: `docs/comp/cli.md`

## Public operator surface comparison

Reviewed against current official peer docs on `2026-03-28`.

| Operator surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| Package-owned HTTP/1 + HTTP/2 + HTTP/3 stack | C-OP | S | P | S | Granian publicly scopes HTTP/1 and HTTP/2; Hypercorn scopes HTTP/3 as optional/qualified. |
| Package-owned TLS 1.3 + X.509 + OCSP / CRL controls | C-OP | P | P | P | tigrcorn is the only server in this set with a package-owned, release-certified TLS/X.509/OCSP/CRL story. |
| Package-owned QUIC / RFC 9220 certification | C-OP | — | P | — | tigrcorn is the only one here with a published release certification bundle for HTTP/3 + RFC 9220. |
| Static offload as first-class server surface | C-OP | — | — | S | Granian and tigrcorn both expose server-native static delivery. |
| ASGI `http.response.pathsend` | C-OP | — | — | S | Granian and tigrcorn both document pathsend. |
| Lifecycle hook contract | C-OP | — | — | P | Granian documents embeddable server hooks; tigrcorn now documents a public lifecycle contract. |
| Embedded / programmatic server contract | C-OP | P | S | S | Uvicorn exposes `uvicorn.run`; Hypercorn documents `serve`; Granian documents embedded `Server`; tigrcorn documents `EmbeddedServer`. |
| Pipe / inproc / raw framed listeners | C-OP | — | — | — | tigrcorn-only transport/operator surface. |
| Proxy normalization as first-class CLI | C-OP | S | M | M | Hypercorn and Granian push proxy handling into wrappers/middleware. |
| Metrics exporter surface | C-OP | — | S | S | Hypercorn publishes StatsD; Granian publishes Prometheus metrics. |
| Machine-readable flag surface | C-OP | — | — | — | tigrcorn ships `cli_flag_surface.json` and related contracts. |
| Machine-readable promotion gate | C-OP | — | — | — | tigrcorn ships evaluators plus release-root manifests/indexes/summaries. |
| Current-state chain + release-root manifests | C-OP | — | — | — | tigrcorn has explicit current-state chain and frozen release roots. |
| Governed mutable / immutable repo markers | C-OP | — | — | — | Introduced in this checkpoint for tigrcorn. |
| Release governance and cert promotion playbook | C-OP | — | — | — | Introduced in this checkpoint for tigrcorn. |

Companion source: `docs/comp/ops.md`

## Outside-boundary matrices

These surfaces are intentionally outside tigrcorn's current T/P/A/D/R product boundary.

### Outside-boundary RFC targets

| Surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| RFC 9218 Extensible Priorities | O | — | — | — | Outside the tigrcorn boundary; Hypercorn's docs mention HTTP/2 prioritisation but not RFC 9218. |
| RFC 9111 HTTP caching/freshness | O | — | — | — | Outside tigrcorn's direct origin/runtime boundary. |
| RFC 9530 Digest Fields | O | — | — | — | Outside tigrcorn's current boundary. |
| RFC 9421 HTTP Message Signatures | O | — | — | — | Outside tigrcorn's current boundary. |
| RFC 7515 / RFC 7516 / RFC 7519 JOSE stack | O | — | — | — | Non-core product layer for this repository. |
| RFC 8152 / RFC 9052 COSE stack | O | — | — | — | Non-core product layer for this repository. |

### Outside-boundary CLI feature families

| Surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| HTTP parser/backend selector | O | S | — | — | Uvicorn exposes `--http auto|h11|httptools`. |
| WebSocket engine selector | O | S | — | — | Uvicorn exposes `--ws ...`; tigrcorn intentionally does not. |
| Alternate interface selector (ASGI2/WSGI/RSGI) | O | S | S | S | tigrcorn stays ASGI3-only; peers expose broader interface selection. |
| Trio runtime / worker selection | O | — | S | — | Hypercorn documents trio workers; tigrcorn keeps Trio out of bounds. |
| Runtime topology / task-engine selector | O | — | — | S | Granian exposes runtime mode and task implementation knobs. |
| TLS protocol-min downgrade selector | O | S | — | S | Uvicorn exposes `--ssl-version`; Granian exposes `--ssl-protocol-min`; tigrcorn keeps downgrade policy out of bounds. |

### Outside-boundary public operator surfaces

| Surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| Parser pluggability as public product surface | O | S | — | — | Uvicorn publicly selects HTTP parsers; tigrcorn keeps parser pluggability out of bounds. |
| WebSocket engine pluggability | O | S | — | — | Uvicorn publicly selects WebSocket engines; tigrcorn keeps this out of bounds. |
| ASGI2 / WSGI / RSGI hosting families | O | S | S | S | tigrcorn stays ASGI3-only by policy. |
| Trio runtime family | O | — | S | — | Hypercorn documents trio workers; tigrcorn excludes Trio. |
| Runtime thread-topology / task-engine family | O | — | — | S | Granian exposes runtime mode and task implementation; tigrcorn excludes this family. |
| Gateway-style caching / integrity / signature behavior | O | — | — | — | tigrcorn keeps cache/integrity/signature gateways out of product scope. |

Companion source: `docs/comp/oob.md`

## Where to look

| Path | Purpose |
|---|---|
| `AGENTS.md` | agent-facing operating guide: where to start, how to validate, how to certify, how to promote, how mutability works |
| `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` | canonical human-readable point-in-time repository summary |
| `docs/README.md` | mutable documentation entrypoint |
| `docs/adr/README.md` | architecture-decision index |
| `docs/gov/README.md` | governance index; layout, naming, mutability, commit/PR/release rules |
| `docs/gov/tree.md` | sustainable repo layout, path limits, pointer rules, root-cleanliness rules |
| `docs/gov/mut.md` | mutable/immutable folder governance and flip rules |
| `docs/gov/release.md` | versioning, certification, promotion, and release-close workflow |
| `docs/notes/inprog.md` | mutable notes on what remains, what is frozen, and what is out of scope |
| `docs/review/conformance/README.md` | certification/conformance index |
| `docs/review/conformance/CERTIFICATION_BOUNDARY.md` | authoritative in-bounds statement |
| `docs/review/conformance/BOUNDARY_NON_GOALS.md` | authoritative out-of-bounds statement |
| `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md` | in-bounds future backlog after promotion |
| `docs/review/conformance/releases/0.3.9/release-0.3.9/` | canonical frozen promoted release artifacts for the repo line |
| `docs/review/conformance/releases/0.3.8/release-0.3.8/` | frozen previously released historical artifacts |
| `docs/review/conformance/CLI_FLAG_SURFACE.md` | human-readable CLI flag surface |
| `docs/review/conformance/cli_flag_surface.json` | machine-readable CLI flag surface |
| `docs/review/conformance/flag_contracts.json` | flag contracts used for promotion checks |
| `docs/review/conformance/flag_covering_array.json` | combinatorial flag coverage model |
| `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` | scoped RFC applicability and competitor comparison audit |
| `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md` | broader applicability / roadmap / competitor-positioning companion |
| `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md` | preserved historical execution plan and closure record |
| `docs/review/conformance/phase9_implementation_plan.current.json` | machine-readable historical execution-plan snapshot |
| `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` | public lifecycle and `EmbeddedServer` contract |
| `src/tigrcorn/` | implementation source |
| `examples/` | runnable examples; `examples/advanced_delivery/` is current, `examples/advanced_protocol_delivery/` is archival compatibility |
| `tests/` | unit, integration, promotion, and documentation verification |
| `tools/` | local helpers, release utilities, governance checker |
| `tools/govchk.py` | mutable/immutable and naming/path-limit checker |

## Governance and repo cleanliness

The repository now distinguishes between **mutable working trees** and **immutable release/evidence trees**.

- Folder state is marked with `MUT.json`.
- Resolution is nearest-ancestor-wins.
- States are `mutable`, `immutable`, and `mixed`.
- Run `python tools/govchk.py state PATH` to resolve a folder state.
- Run `python tools/govchk.py scan` to check naming/path limits on mutable non-exempt paths.

Rules for **new or renamed mutable paths**:

- file name length `<= 24`
- folder name length `<= 16`
- full relative path length `<= 120`

The prior root current-state / delivery-note / RFC-report Markdown sprawl has been migrated into `docs/review/conformance/state/`, `docs/review/conformance/delivery/`, and `docs/review/conformance/reports/`. Preserved release/conformance trees remain in-tree for provenance and test stability; they are not a license to create new path/name sprawl.

## Public lifecycle and embedded use

The public lifecycle and embedder contract is documented in `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`.

That document freezes:

- `on_startup`, `on_shutdown`, and `on_reload`
- ordering relative to `lifespan.startup()` and `lifespan.shutdown()`
- failure semantics
- `EmbeddedServer` behavior and examples

## Running

Basic run:

```bash
python -m tigrcorn examples.echo_http.app:app
```

HTTP/3 / QUIC example:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem
```

HTTP/3 / QUIC with mTLS-style client certificate verification:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem --ssl-ca-certs client-ca.pem --ssl-require-client-cert
```

HTTP/3 / QUIC with Retry enabled:

```bash
python -m tigrcorn examples.echo_http.app:app --transport udp --protocol http3 --http 3 --port 9443 --ssl-certfile cert.pem --ssl-keyfile key.pem --quic-require-retry
```

## Validation and promotion

Promotion-relevant validation typically includes:

```bash
python -m compileall -q src benchmarks tools
pytest -q
python - <<'PY'
from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target
print(evaluate_release_gates('.').passed)
print(evaluate_release_gates('.', boundary_path='docs/review/conformance/certification_boundary.strict_target.json').passed)
print(evaluate_promotion_target('.').passed)
PY
```

For detailed release workflow rules, see `docs/gov/release.md`. For agentic execution rules, see `AGENTS.md`.

## Current-state and historical planning notes

Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current truth.

Use the following preserved records for historical planning/provenance, not as competing current-state sources:

- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/phase9_implementation_plan.current.json`
- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`

The repo line is `0.3.9`. External publication remains an operator action outside the repository; consult the package index before claiming a new publish has occurred.


## Phase 9I release assembly and certifiable checkpoint

The executed Phase 9I release-assembly checkpoint is now documented through:

- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- `docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`


## Certification environment freeze

The strict-promotion release workflow now freezes the certification environment before it invokes any Phase 9 checkpoint script. Current documentation and preserved artifacts live in:

- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`
- `docs/review/conformance/delivery/DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md`
