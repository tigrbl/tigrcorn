<div align="center">

<img
  src="https://github.com/Tigrbl/tigrcorn/blob/68c5baadd745555de1c6bee70d9b9f3763a7ed3c/assets/tigrcorn_brand_frag_light.png?raw=1"
  alt="Tigrcorn light branding fragment"
/>

> Package-owned ASGI3 transport server with audited protocol, operator, release, and certification surfaces.

---
</div>

<p align="center">
<a href="https://pypi.org/project/tigrcorn/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/tigrcorn?label=PyPI"></a> 
<a href="https://pypi.org/project/tigrcorn/"><img alt="PyPI downloads" src="https://img.shields.io/pepy/dt/tigrcorn?label=downloads"></a> 
<a href="https://hits.sh/github.com/tigrbl/tigrcorn"><img alt="Project hits badge" src="https://hits.sh/github.com/tigrbl/tigrcorn.svg?label=hits"></a>
<a href="docs/review/conformance/releases/0.3.9/release-0.3.9/"><img alt="repo line 0.3.9" src="https://img.shields.io/badge/repo_line-0.3.9-2f7ed8"></a> 
<a href="LICENSE"><img alt="license Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.11 supported" src="https://img.shields.io/badge/python-3.11-3776ab"></a> <a href="pyproject.toml"><img alt="Python 3.12 supported" src="https://img.shields.io/badge/python-3.12-3776ab"></a> 
</p>


<p align="center">
<a href="docs/review/conformance/CERTIFICATION_BOUNDARY.md"><img alt="authoritative boundary green" src="https://img.shields.io/badge/authoritative_boundary-green-1f883d"></a> <a href="docs/review/conformance/STRICT_PROFILE_TARGET.md"><img alt="strict profile green" src="https://img.shields.io/badge/strict_profile-green-1f883d"></a> <a href="docs/review/conformance/releases/0.3.9/release-0.3.9/"><img alt="promotion green" src="https://img.shields.io/badge/promotion-green-1f883d"></a> <a href="AGENTS.md"><img alt="agents documented" src="https://img.shields.io/badge/agents-documented-6f42c1"></a>
</p>

---

<p align="center">
Tigrcorn is an ASGI3 server whose core transport, protocol, lifecycle, delivery, and operator behavior stays inside the package instead of being delegated to a loose stack of external wrappers. In practice that means the project is opinionated about owning the parts that operators and reviewers actually need to reason about: listener setup, protocol selection, TLS and QUIC controls, static and entity semantics, lifecycle hooks, release gates, and preserved certification artifacts.

Tigrcorn exists because “supports protocol X” is not enough for a serious server. Operators need to know **what is inside the product boundary**, implementers need stable public surfaces, maintainers need auditable release gates, and reviewers need frozen evidence roots that are not rewritten after promotion. The repository therefore distinguishes between the **authoritative certification boundary**, the broader **public/operator surface**, mutable current-state docs, and immutable release roots. That boundary discipline is what lets the repository say, in its own current-state records, that the package is **certifiably fully RFC compliant under the authoritative certification boundary** and that the canonical `0.3.9` promoted root is **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.[^boundary]
</p>

## Table of contents

- [Status at a glance](#status-at-a-glance)
- [What Tigrcorn is](#what-tigrcorn-is)
- [Why Tigrcorn exists](#why-tigrcorn-exists)
- [Package boundary, evidence tiers, and support model](#package-boundary-evidence-tiers-and-support-model)
- [Installation and optional dependency surface](#installation-and-optional-dependency-surface)
- [Protocol and feature map](#protocol-and-feature-map)
- [CLI usage](#cli-usage)
- [Public operator and programmatic usage](#public-operator-and-programmatic-usage)
- [Matrix legend and comparison matrices](#matrix-legend-and-comparison-matrices)
- [Where to look](#where-to-look)
- [Authoring and maintainer workflow](#authoring-and-maintainer-workflow)
- [Governance and repo cleanliness](#governance-and-repo-cleanliness)
- [Validation and promotion](#validation-and-promotion)
- [Current-state and historical planning](#current-state-and-historical-planning)
- [Certification environment freeze](#certification-environment-freeze)
- [Contributing, conduct, and community norms](#contributing-conduct-and-community-norms)
- [Footnotes](#footnotes)

## Status at a glance

| Topic | Current state | Primary source |
|---|---|---|
| Repo line | `0.3.9` | `pyproject.toml`, `src/tigrcorn/version.py` |
| Canonical release root | `docs/review/conformance/releases/0.3.9/release-0.3.9/` | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` |
| Historical promoted root kept for provenance | `docs/review/conformance/releases/0.3.8/release-0.3.8/` | release history in `docs/review/conformance/releases/` |
| Authoritative boundary | green | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| Strict profile | green | `docs/review/conformance/STRICT_PROFILE_TARGET.md` |
| Promotion target | green | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` |
| Current package claim | **certifiably fully RFC compliant under the authoritative certification boundary**[^boundary] | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` |
| Promoted-root claim | **strict-target certifiably fully RFC compliant** and **certifiably fully featured** | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` |
| Current-state entrypoint | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` | canonical human current-state source |
| Machine-readable current-state chain | `docs/review/conformance/current_state_chain.current.json` | canonical machine current-state source |
| Operator docs | `docs/ops/README.md`, `docs/ops/cli.md`, `docs/ops/public.md` | operator-focused mutable docs |
| Lifecycle/embedder contract | `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` | public lifecycle and `EmbeddedServer` contract |
| Maintainer/authoring docs | `docs/gov/authoring.md`, `CONTRIBUTING.md` | authoring and repo workflow |
| Certification environment freeze | `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md` | frozen release-workflow contract[^freeze] |


## What Tigrcorn is

Tigrcorn is the server package for teams that want the **runtime entrypoint**, the **listener model**, the **RFC-facing protocol claims**, the **operator flags**, and the **promotion/release evidence** to line up in one place.

It provides, in the current public surface:

- ASGI3 execution with package-owned HTTP/1.1, HTTP/2, HTTP/3, QUIC, and WebSocket carriers.
- Operator-facing CLI and config assembly for listener binding, TLS, QUIC, logging, metrics, static delivery, resource limits, proxy normalization, reload, and workers.
- Programmatic entrypoints for direct execution (`run`, `serve`, `serve_import_string`), embedding (`EmbeddedServer`), static mounting (`StaticFilesApp`, `mount_static_app`), config construction (`build_config*`), and release/promotion evaluation (`evaluate_release_gates`, `evaluate_promotion_target`).
- Current-state, planning, and release-artifact discipline under `docs/review/conformance/` and immutable versioned release roots.

The package is intentionally **not** a “support everything” server. Several families remain explicit non-goals or outside-boundary work, including Trio runtime support, WSGI/ASGI2/RSGI compatibility layers, parser pluggability, WebSocket engine pluggability, JOSE/COSE, RFC 9111 caching, RFC 9530, RFC 9421, and other out-of-scope items called out in `docs/review/conformance/BOUNDARY_NON_GOALS.md`.

## Why Tigrcorn exists

Three constraints shape the project:

1. **Boundary clarity.** Tigrcorn separates what is certified in the RFC claim from what is available in the broader operator surface. This is the role of `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, `docs/review/conformance/STRICT_PROFILE_TARGET.md`, and `docs/review/conformance/BOUNDARY_NON_GOALS.md`.
2. **Auditable releases.** The project keeps canonical promoted roots under `docs/review/conformance/releases/0.3.9/release-0.3.9/` and older preserved roots such as `docs/review/conformance/releases/0.3.8/release-0.3.8/`. Mutable work happens elsewhere; frozen roots stay frozen.
3. **Operator-grade truth.** The CLI, config model, public lifecycle contract, current-state chain, promotion contract, and environment freeze are all documented and checkpointed so operators, maintainers, and reviewers do not have to infer product truth from implementation accidents.

## Package boundary, evidence tiers, and support model

### Boundary model

Tigrcorn uses a T/P/A/D/R style boundary language across the repository. For a concise operational reading:

| Slice | Meaning in this repository | Canonical source |
|---|---|---|
| `T` | transport and listener ownership | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| `P` | protocol implementation and RFC-scoped behavior | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| `A` | ASGI3 application interface boundary | `docs/adr/0001-preserve-asgi-boundary.md` |
| `D` | delivery/entity semantics and public operator surface | `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, `docs/ops/public.md` |
| `R` | release, promotion, and preserved evidence/provenance | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`, `docs/gov/release.md` |

The **authoritative certification boundary** is the contract for RFC-scoped claims. The **strict profile** is a stricter promoted-root target. The **public/operator surface** is broader and includes valuable operational capabilities that are intentionally not all part of the RFC certification claim.

### Evidence tiers

| Tier | Meaning | Primary sources |
|---|---|---|
| `local_conformance` | package-owned local validation and repo-side conformance evidence | `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, `docs/review/conformance/README.md` |
| `same_stack_replay` | preserved replay evidence against the package stack | `docs/review/conformance/external_matrix.same_stack_replay.json` |
| `independent_certification` | preserved third-party / cross-stack evidence used for promoted release claims | `docs/review/conformance/external_matrix.release.json`, `docs/review/conformance/external_matrix.current_release.json` |

Promotion is not a fourth evidence tier. It is the result of the release-gate and promotion-target evaluators over the current repository and the canonical promoted root. See `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`, `docs/review/conformance/current_state_chain.current.json`, and `docs/review/conformance/releases/0.3.9/release-0.3.9/`.

### Support model

| Marker | Meaning |
|---|---|
| `C-RFC` | implemented and included inside Tigrcorn's current certified RFC boundary |
| `C-OP` | implemented and included inside Tigrcorn's current certified public/operator surface |
| `O` | intentionally outside Tigrcorn's current product boundary |

Use `docs/review/conformance/CERTIFICATION_BOUNDARY.md` for the normative claim boundary and `docs/review/conformance/BOUNDARY_NON_GOALS.md` for excluded families.

## Installation and optional dependency surface

### Base install

```bash
python -m pip install tigrcorn
```

### Development / certification install

```bash
python -m pip install -e ".[certification,dev]"
```

This is the frozen install contract referenced by `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md` and `docs/review/conformance/certification_environment_freeze.current.json`.

### Optional extras

| Extra | Public status | Purpose | Declared dependencies |
|---|---|---|---|
| `config-yaml` | supported | Enable .yaml/.yml config loading | `PyYAML>=6.0` |
| `compression` | supported | Enable Brotli content coding and .br static sidecars | `brotli>=1.1.0` |
| `runtime-uvloop` | supported | Enable --runtime uvloop | `uvloop>=0.19.0; platform_system != 'Windows'` |
| `runtime-trio` | declared not supported | Reserved dependency path for future/internal trio runtime work | `trio>=0.25.0` |
| `full-featured` | supported | Aggregate the current public optional feature surface | `PyYAML>=6.0`, `brotli>=1.1.0`, `uvloop>=0.19.0; platform_system != 'Windows'` |
| `certification` | supported | Certification/interoperability tooling and preserved peer paths | `aioquic>=1.3.0`, `h2>=4.1.0`, `websockets>=12.0`, `wsproto>=1.3.0` |
| `dev` | supported | Repository development and checkpoint validation | `pytest>=8.0`, `aioquic>=1.3.0`, `h2>=4.1.0`, `websockets>=12.0`, `wsproto>=1.3.0`, `PyYAML>=6.0`, `brotli>=1.1.0`, `uvloop>=0.19.0; platform_system != 'Windows'` |

### Practical install examples

```bash
# YAML config support
python -m pip install -e ".[config-yaml]"

# Brotli content-coding + precompressed sidecars
python -m pip install -e ".[compression]"

# uvloop runtime option (non-Windows)
python -m pip install -e ".[runtime-uvloop]"

# current aggregate operator feature surface
python -m pip install -e ".[full-featured]"
```

Notes:

- `runtime-trio` is declared but remains **not supported** in the current public runtime surface.
- The release workflow currently supports Python `3.11` and `3.12`; the local recorded environment snapshot in this workspace is documented in the freeze files.[^freeze]
- See `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md` for the authoritative optional dependency truth source.

## Protocol and feature map

| Area | Surface | Status | Primary docs / examples |
|---|---|---|---|
| Core protocol | HTTP/1.1 (`RFC 9112`) | `C-RFC` | `docs/protocols/http1.md`, `examples/echo_http/app.py` |
| Core protocol | HTTP/2 (`RFC 9113`) | `C-RFC` | `docs/protocols/http2.md`, `docs/review/conformance/DEPLOYMENT_PROFILES.md` |
| Core protocol | HTTP/3 + QUIC (`RFC 9114`, `RFC 9000`, `RFC 9001`, `RFC 9002`) | `C-RFC` | `docs/protocols/http3.md`, `docs/protocols/quic.md` |
| WebSocket carriers | RFC 6455 / RFC 8441 / RFC 9220 | `C-RFC` | `docs/protocols/websocket.md`, `examples/websocket_echo/app.py` |
| Delivery/origin | CONNECT relay, trailer fields, content coding | `C-RFC` | `docs/review/conformance/DEPLOYMENT_PROFILES.md`, `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| Delivery/origin | Conditional requests, range requests, Early Hints, bounded Alt-Svc | `C-RFC` | `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`, `examples/advanced_protocol_delivery/` |
| Security | TLS 1.3, ALPN, X.509, OCSP, CRL | `C-RFC` | `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md` |
| Static delivery | `StaticFilesApp`, mounted static path, precompressed sidecars | `C-OP` | `examples/http_entity_static/app.py`, `docs/ops/public.md` |
| Embedding | `EmbeddedServer`, startup/shutdown/reload hooks | `C-OP` | `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`, `examples/advanced_protocol_delivery/runtime_embedding.py` |
| Operator control | reload, workers, runtime selection, logging, metrics, proxy normalization | `C-OP` | `docs/ops/cli.md`, `docs/review/conformance/CLI_FLAG_SURFACE.md` |
| Custom transports | pipe / inproc / rawframed / custom | `C-OP` inside the operator surface, outside the strict RFC claim where noted | `docs/ops/cli.md`, `docs/review/conformance/BOUNDARY_NON_GOALS.md` |


## CLI usage

The primary executable is `tigrcorn`. The external interoperability runner is `tigrcorn-interop`.

For the exhaustive operator reference, read:

- `docs/ops/cli.md`
- `docs/review/conformance/CLI_FLAG_SURFACE.md`
- `docs/review/conformance/DEPLOYMENT_PROFILES.md`
- `docs/review/conformance/cli_help.current.txt`
- `docs/review/conformance/tigrcorn_interop_help.current.txt`

### CLI truth model

Tigrcorn's config precedence remains:

```text
CLI > env > config file > defaults
```

That rule is documented in `docs/gov/code.md` and implemented by the config loaders exposed through `build_config_from_sources`.

### Common launch patterns

#### Minimal HTTP/1.1 + HTTP/2 server

```bash
tigrcorn examples.echo_http.app:app --host 127.0.0.1 --port 8000
```

#### App factory loading

```bash
tigrcorn examples.echo_http.app:create_app --factory --host 127.0.0.1 --port 8000
```

#### Config file + environment merge

```bash
tigrcorn examples.echo_http.app:app \
  --config ./tigrcorn.toml \
  --env-file ./.env \
  --env-prefix TIGRCORN
```

#### HTTP/2 over TLS

```bash
tigrcorn examples.echo_http.app:app \
  --host 127.0.0.1 \
  --port 8443 \
  --http 2 \
  --ssl-certfile ./certs/server.pem \
  --ssl-keyfile ./certs/server.key
```

#### HTTP/3 / QUIC

```bash
tigrcorn examples.echo_http.app:app \
  --quic-bind 127.0.0.1:8443 \
  --http 3 \
  --protocol http3 \
  --protocol quic \
  --ssl-certfile ./certs/server.pem \
  --ssl-keyfile ./certs/server.key
```

#### HTTP/3 / QUIC with client-certificate verification

```bash
tigrcorn examples.echo_http.app:app \
  --quic-bind 127.0.0.1:8443 \
  --http 3 \
  --protocol http3 \
  --protocol quic \
  --ssl-certfile ./certs/server.pem \
  --ssl-keyfile ./certs/server.key \
  --ssl-ca-certs ./certs/ca.pem \
  --ssl-require-client-cert
```

#### WebSocket compression

```bash
tigrcorn examples.websocket_echo.app:app \
  --host 127.0.0.1 \
  --port 9000 \
  --websocket-compression permessage-deflate
```

#### Static route mounting

```bash
tigrcorn examples.http_entity_static.app:app \
  --static-path-route /assets \
  --static-path-mount ./public \
  --static-path-index-file index.html \
  --static-path-expires 3600
```

#### CONNECT relay, trailer, and content-coding policies

```bash
tigrcorn examples.echo_http.app:app \
  --connect-policy allowlist \
  --connect-allow 127.0.0.1:5432 \
  --trailer-policy strict \
  --content-coding-policy allowlist \
  --content-codings br,gzip,deflate
```

#### Automatic Alt-Svc advertisement for HTTP/3-capable UDP listeners

```bash
tigrcorn examples.advanced_protocol_delivery.alt_svc_app:app \
  --bind 127.0.0.1:8080 \
  --quic-bind 127.0.0.1:8443 \
  --http 1.1 --http 2 --http 3 \
  --alt-svc-auto \
  --alt-svc-ma 86400 \
  --alt-svc-persist
```

#### Metrics and structured logging

```bash
tigrcorn examples.echo_http.app:app \
  --structured-log \
  --metrics \
  --metrics-bind 127.0.0.1:9100 \
  --statsd-host 127.0.0.1:8125 \
  --otel-endpoint http://127.0.0.1:4318
```

#### Workers, reload, and runtime selection

```bash
tigrcorn examples.echo_http.app:app \
  --workers 4 \
  --runtime auto \
  --reload \
  --reload-dir ./src \
  --reload-include '*.py' \
  --reload-exclude '*.tmp'
```

#### Interoperability matrix execution

```bash
tigrcorn-interop \
  --matrix docs/review/conformance/external_matrix.release.json \
  --output ./artifacts/interop
```

Use `--matrix docs/review/conformance/external_matrix.current_release.json` to run the current-release bundle contract, or `--matrix docs/review/conformance/external_matrix.same_stack_replay.json` for preserved same-stack replay coverage.

## Public operator and programmatic usage

The package's most important public import surfaces are documented in full in `docs/ops/public.md` and `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`.

### Top-level imports

```python
from tigrcorn import EmbeddedServer, StaticFilesApp, run, serve, serve_import_string
from tigrcorn.config import build_config, build_config_from_sources
from tigrcorn.static import mount_static_app, normalize_static_route
from tigrcorn.compat.release_gates import (
    assert_promotion_target_ready,
    assert_release_ready,
    evaluate_promotion_target,
    evaluate_release_gates,
)
```

### Run from code

```python
from tigrcorn import run

run(
    "examples.echo_http.app:app",
    host="127.0.0.1",
    port=8000,
    http_versions=["1.1", "2"],
)
```

### Async serve with an in-memory ASGI app

```python
from tigrcorn import serve

async def app(scope, receive, send):
    ...

await serve(app, host="127.0.0.1", port=8000)
```

### Serve from an import string inside an existing async runtime

```python
from tigrcorn import serve_import_string

await serve_import_string(
    "examples.websocket_echo.app:app",
    host="127.0.0.1",
    port=9000,
)
```

### Embedded lifecycle control

```python
from tigrcorn import EmbeddedServer
from tigrcorn.config import build_config

config = build_config(host="127.0.0.1", port=0, lifespan="on")

async with EmbeddedServer(app, config) as embedded:
    print(embedded.listeners)
    print(embedded.bound_endpoints())
```

The lifecycle ordering, hook contract, idempotent `start()`, no-op `close()` before startup, and failure semantics are defined in `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`.

### Static delivery composition

```python
from tigrcorn.static import mount_static_app

app = mount_static_app(
    app,
    route="/assets",
    directory="./public",
    apply_content_coding=True,
    content_coding_policy="allowlist",
)
```

### Config assembly

```python
from tigrcorn.config import build_config_from_sources

config = build_config_from_sources(
    config_path="./tigrcorn.toml",
    env_prefix="TIGRCORN",
    env_file=".env",
    cli_overrides={
        "app": {"target": "examples.echo_http.app:app"},
        "logging": {"level": "debug"},
    },
)
```

### Release and promotion evaluation

```python
from tigrcorn.compat.release_gates import evaluate_promotion_target, evaluate_release_gates

release_report = evaluate_release_gates(".")
promotion_report = evaluate_promotion_target(".")

print(release_report.passed)
print(promotion_report.passed)
```

## Matrix legend and comparison matrices

The matrices below are kept in the README for “status at a glance” reading, with maintained companion sources under `docs/comp/`.

> [!NOTE]
> The legend below applies to the comparison matrices. `C-RFC` and `C-OP` describe Tigrcorn status inside this repository's own documented certification or operator boundary. Peer cells are documentation snapshots reviewed on `2026-03-28`, not repository-issued certifications.[^peers]

### Matrix legend

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

<details open>
<summary><strong>RFC target comparison</strong></summary>

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

</details>

<details open>
<summary><strong>CLI feature comparison</strong></summary>

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

</details>

<details open>
<summary><strong>Public operator surface comparison</strong></summary>

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

</details>

<details open>
<summary><strong>Outside-boundary matrices</strong></summary>

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

</details>


## Where to look

| If you are… | Start here | Then go to |
|---|---|---|
| Operator launching the server | `docs/ops/cli.md` | `docs/review/conformance/DEPLOYMENT_PROFILES.md`, `docs/review/conformance/CLI_FLAG_SURFACE.md` |
| Embedder / application developer | `docs/ops/public.md` | `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`, `examples/advanced_protocol_delivery/runtime_embedding.py` |
| Static/delivery implementer | `examples/http_entity_static/app.py` | `docs/ops/public.md`, `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` |
| Maintainer / release owner | `docs/gov/authoring.md` | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`, `docs/gov/release.md` |
| Certification / audit reviewer | `docs/review/conformance/README.md` | `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, `docs/review/conformance/releases/0.3.9/release-0.3.9/` |
| Author writing new docs | `CONTRIBUTING.md` | `docs/gov/authoring.md`, `docs/gov/tree.md`, `docs/gov/mut.md` |
| Agent / automation | `AGENTS.md` | `docs/review/conformance/current_state_chain.current.json`, `tools/govchk.py` |
| Contributor looking for current truth | `docs/review/conformance/state/README.md` | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`, `docs/review/conformance/state/checkpoints/` |


## Authoring and maintainer workflow

The repository now has a dedicated maintainer/authoring guide:

- `docs/gov/authoring.md` — documentation ownership, truth hierarchy, update triggers, and maintainer checklist
- `CONTRIBUTING.md` — contributor workflow, validation checklist, and change expectations
- `AGENTS.md` — repo operating instructions for agents/automation
- `docs/gov/release.md` — release and promotion governance
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` — canonical human current-state truth
- `docs/review/conformance/current_state_chain.current.json` — canonical machine current-state truth

Maintainer responsibilities include keeping the following aligned when public behavior changes:

1. code
2. tests
3. machine-readable docs / manifests / JSON truth files
4. human docs
5. current-state and promotion docs
6. immutable release-root pointers when promotion-relevant

## Governance and repo cleanliness

Repository cleanliness is governed by `MUT.json`, `docs/gov/tree.md`, `docs/gov/mut.md`, and `docs/gov/code.md`.

### Core rules

- Root docs stay narrow: `README.md`, `AGENTS.md`, release notes, packaging/build roots, and community entrypoints such as `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.
- New mutable docs belong under short, purpose-scoped folders in `docs/`, including `docs/ops/`, `docs/gov/`, `docs/comp/`, `docs/review/`, `docs/protocols/`, `docs/architecture/`, and `docs/adr/`.
- Immutable release roots are not development workspaces.
- New or renamed mutable paths follow the repo path policy: file name `<= 24`, folder name `<= 16`, full relative path `<= 120`.
- Mutability uses a nearest-ancestor-wins `MUT.json` rule.

### Useful governance commands

```bash
python tools/govchk.py state README.md
python tools/govchk.py state docs/review/conformance/releases/0.3.9
python tools/govchk.py scan
```

## Validation and promotion

A practical maintainer validation pass looks like this:

```bash
python tools/govchk.py scan
PYTHONPATH=src python -m compileall -q src benchmarks tools
PYTHONPATH=src pytest -q
```

Promotion-facing evaluators:

```bash
PYTHONPATH=src python - <<'PY'
from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target

print(evaluate_release_gates('.').passed)
print(
    evaluate_release_gates(
        '.',
        boundary_path='docs/review/conformance/certification_boundary.strict_target.json',
    ).passed
)
print(evaluate_promotion_target('.').passed)
PY
```

Read next:

- `docs/gov/release.md`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/STRICT_PROFILE_TARGET.md`
- `docs/review/conformance/FLAG_CERTIFICATION_TARGET.md`
- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`

## Current-state and historical planning

For current package truth, start with:

- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/state/README.md`
- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`

For historical planning and release-provenance checkpoints, use:

- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/phase9_implementation_plan.current.json`
- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md`
- `docs/review/conformance/phase9a_execution_backlog.current.json`
- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- `docs/review/conformance/state/checkpoints/`

These planning and checkpoint files explain **how the repository got to the current promoted state** and what constraints were in force at each checkpoint. They are historical and operational provenance; they do not replace the canonical current-state pointer.

## Certification environment freeze

The certification-environment freeze documents the install contract and runtime prerequisites for the strict release workflow and preserved certification bundle.

Start here:

- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/delivery/DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`
- `.github/workflows/phase9-certification-release.yml`
- `tools/run_phase9_release_workflow.py`

Frozen install command:

```bash
python -m pip install -e ".[certification,dev]"
```

The current recorded snapshot freezes the workflow contract even though the live checked environment in this repository reports a missing `aioquic` import. The freeze files make that distinction explicit instead of hiding it.[^freeze]

## Contributing, conduct, and community norms

- `CONTRIBUTING.md` explains how to make changes without breaking the boundary, docs, tests, or release evidence.
- `CODE_OF_CONDUCT.md` defines project participation expectations and reporting guidance.
- `docs/gov/authoring.md` explains how maintainers and authors should update the repository without creating truth conflicts.
- `docs/gov/tree.md` and `docs/gov/mut.md` explain where new files belong and which trees are frozen.

## Footnotes

[^boundary]: Certification language in this repository is scoped by `docs/review/conformance/CERTIFICATION_BOUNDARY.md` and the promoted-root policy described in `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`. Out-of-scope families remain out of scope unless the boundary docs say otherwise.

[^peers]: Peer comparison matrices are documentation snapshots reviewed on `2026-03-28`. They are not vendor attestations, and they should not be read as this repository certifying another project.

[^freeze]: The freeze distinguishes the **authoritative release-workflow contract** from the **observed local environment snapshot**. A preserved release workflow may remain the normative contract even when the current editing environment is missing one certification dependency such as `aioquic`.

[^publish]: Repository promotion, preserved release roots, and external publication are different events. External publication remains an operator action outside the repository, as described in `docs/gov/release.md`.
