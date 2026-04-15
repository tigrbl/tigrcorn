<div align="center">

<img
  src="https://github.com/Tigrbl/tigrcorn/blob/68c5baadd745555de1c6bee70d9b9f3763a7ed3c/assets/tigrcorn_brand_frag_light.png?raw=1"
  alt="Tigrcorn light branding fragment"
/>

> ASGI3 server with built-in HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, TLS, static delivery, and release validation.

---
</div>

<p align="center"><strong>Release status</strong><br>
<a href="docs/review/conformance/releases/0.3.9/release-0.3.9/"><img alt="repo line 0.3.9" src="https://img.shields.io/badge/repo_line-0.3.9-2f7ed8"></a>
<a href="docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md"><img alt="current state canonical" src="https://img.shields.io/badge/current_state-canonical-0969da"></a>
<a href="docs/review/conformance/CERTIFICATION_BOUNDARY.md"><img alt="authoritative boundary green" src="https://img.shields.io/badge/authoritative_boundary-green-1f883d"></a>
<a href="docs/review/conformance/STRICT_PROFILE_TARGET.md"><img alt="strict profile green" src="https://img.shields.io/badge/strict_profile-green-1f883d"></a>
<a href="docs/review/conformance/releases/0.3.9/release-0.3.9/"><img alt="promotion green" src="https://img.shields.io/badge/promotion-green-1f883d"></a>
<a href="AGENTS.md"><img alt="agents documented" src="https://img.shields.io/badge/agents-documented-6f42c1"></a>
</p>

<p align="center"><strong>Package</strong><br>
<a href="https://pypi.org/project/tigrcorn/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/tigrcorn?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn/"><img alt="PyPI downloads" src="https://img.shields.io/badge/downloads-PyPI-blue"></a>
<a href="LICENSE"><img alt="license Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.11 supported" src="https://img.shields.io/badge/python-3.11-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.12 supported" src="https://img.shields.io/badge/python-3.12-3776ab"></a>
<a href="docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md"><img alt="runtime auto supported" src="https://img.shields.io/badge/runtime-auto-0a7f5a"></a>
<a href="docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md"><img alt="runtime asyncio supported" src="https://img.shields.io/badge/runtime-asyncio-0a7f5a"></a>
<a href="docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md"><img alt="runtime uvloop supported" src="https://img.shields.io/badge/runtime-uvloop-0a7f5a"></a>
</p>

<p align="center"><strong>Protocol status</strong><br>
<a href="docs/protocols/http1.md"><img alt="HTTP/1.1 C-RFC" src="https://img.shields.io/badge/HTTP%2F1.1-C--RFC-1f883d"></a>
<a href="docs/protocols/http2.md"><img alt="HTTP/2 C-RFC" src="https://img.shields.io/badge/HTTP%2F2-C--RFC-1f883d"></a>
<a href="docs/protocols/http3.md"><img alt="HTTP/3 C-RFC" src="https://img.shields.io/badge/HTTP%2F3-C--RFC-1f883d"></a>
<a href="docs/protocols/quic.md"><img alt="QUIC C-RFC" src="https://img.shields.io/badge/QUIC-C--RFC-1f883d"></a>
<a href="docs/protocols/websocket.md"><img alt="WebSocket C-RFC" src="https://img.shields.io/badge/WebSocket-C--RFC-1f883d"></a>
<a href="docs/protocols/websocket.md"><img alt="RFC 8441 C-RFC" src="https://img.shields.io/badge/RFC8441-C--RFC-1f883d"></a>
<a href="docs/protocols/websocket.md"><img alt="RFC 9220 C-RFC" src="https://img.shields.io/badge/RFC9220-C--RFC-1f883d"></a>
<a href="docs/review/conformance/CERTIFICATION_BOUNDARY.md"><img alt="TLS 1.3 X.509 OCSP C-RFC" src="https://img.shields.io/badge/TLS1.3_X.509_OCSP-C--RFC-1f883d"></a>
</p>

<p align="center"><strong>Operator and API surface status</strong><br>
<a href="docs/ops/cli.md"><img alt="CLI C-OP" src="https://img.shields.io/badge/CLI-C--OP-0a7f5a"></a>
<a href="docs/LIFECYCLE_AND_EMBEDDED_SERVER.md"><img alt="EmbeddedServer C-OP" src="https://img.shields.io/badge/EmbeddedServer-C--OP-0a7f5a"></a>
<a href="docs/LIFECYCLE_AND_EMBEDDED_SERVER.md"><img alt="Lifecycle hooks C-OP" src="https://img.shields.io/badge/Lifecycle_hooks-C--OP-0a7f5a"></a>
<a href="docs/ops/public.md"><img alt="StaticFilesApp C-OP" src="https://img.shields.io/badge/StaticFilesApp-C--OP-0a7f5a"></a>
<a href="docs/ops/cli.md"><img alt="Workers and reload C-OP" src="https://img.shields.io/badge/Workers_reload-C--OP-0a7f5a"></a>
<a href="docs/ops/cli.md"><img alt="Metrics and logging C-OP" src="https://img.shields.io/badge/Metrics_logging-C--OP-0a7f5a"></a>
<a href="docs/ops/public.md"><img alt="Release gates C-OP" src="https://img.shields.io/badge/Release_gates-C--OP-0a7f5a"></a>
</p>


---

Tigrcorn is an ASGI3 server for teams that want modern transport and protocol support, explicit operator controls, and a public Python API that matches the shipped runtime. It implements HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSockets, TLS handling, static delivery, and release checks inside the project, with operator docs and current-state material kept alongside the code.


## Table of contents

- [Legend](#legend)
- [Quick start](#quick-start)
- [Why teams pick Tigrcorn](#why-teams-pick-tigrcorn)
- [What Tigrcorn provides](#what-tigrcorn-provides)
- [Installation and extras](#installation-and-extras)
- [Protocol and feature map](#protocol-and-feature-map)
- [CLI usage](#cli-usage)
- [Public API and embedding usage](#public-api-and-embedding-usage)
- [Current scope](#current-scope)
- [Status at a glance](#status-at-a-glance)
- [Validation and promotion](#validation-and-promotion)
- [Where to look](#where-to-look)
- [Governance and maintainer workflow](#governance-and-maintainer-workflow)
- [Current-state and historical planning](#current-state-and-historical-planning)
- [Certification environment freeze](#certification-environment-freeze)
- [Contributing, conduct, and community norms](#contributing-conduct-and-community-norms)
- [Footnotes](#footnotes)

## Legend

Use this legend for the badges, status tables, and scope markers in this README.

| Marker | Meaning |
|---|---|
| `C-RFC` | included in Tigrcorn's current certified RFC boundary |
| `C-OP` | included in Tigrcorn's current public operator/API surface |
| `O` | outside Tigrcorn's current documented scope |
| `green` | the referenced repo contract or evaluation target is currently passing |
| `canonical` | the referenced document is the current mutable source of truth |
| `repo_line` | the active repository release line represented by this checkout |
| `runtime-auto`, `runtime-asyncio`, `runtime-uvloop` | documented runtime modes in the current public surface |

The top badge groups use plain language labels where possible. The protocol and feature tables use `C-RFC`, `C-OP`, and `O` as compact scope markers.

## Quick start

### Install

```bash
python -m pip install tigrcorn
```

### Run an HTTP server

```bash
tigrcorn examples.echo_http.app:app --host 127.0.0.1 --port 8000
```

### Run HTTP/3 + QUIC

```bash
tigrcorn examples.echo_http.app:app \
  --quic-bind 127.0.0.1:8443 \
  --http 3 \
  --protocol http3 \
  --protocol quic \
  --ssl-certfile ./certs/server.pem \
  --ssl-keyfile ./certs/server.key
```

### Run from Python

```python
from tigrcorn import run

run("examples.echo_http.app:app", host="127.0.0.1", port=8000)
```

For complete operator recipes, use `docs/ops/cli.md`. For public imports and lifecycle details, use `docs/ops/public.md` and `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`.
For the blessed safe deployment profiles, use `docs/ops/profiles.md` and the generated `profiles/*.profile.json` artifacts.

## Why teams pick Tigrcorn

- **Modern protocol stack in the server itself.** HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSockets, TLS 1.3, ALPN, X.509 validation, OCSP, and CRL handling are first-class documented surfaces.
- **Operator features that matter in deployment.** Listener binding, TLS and QUIC controls, workers, reload, structured logging, metrics, proxy normalization, content-coding policy, CONNECT policy, Early Hints, Alt-Svc, and static delivery are part of the public surface.
- **A public Python API for applications and hosts.** `run`, `serve`, `serve_import_string`, `EmbeddedServer`, `StaticFilesApp`, and the config helpers are documented as importable entrypoints.
- **Static delivery and entity semantics built into the package.** Static mounting, precompressed sidecars, conditional requests, range requests, and response-path helpers are available without a separate static server wrapper.
- **Release and promotion checks in the repo.** `evaluate_release_gates` and `evaluate_promotion_target` are shipped APIs, and the repo preserves current-state and promoted-release material under `docs/review/conformance/`.

## What Tigrcorn provides

| Area | What you get | Primary docs |
|---|---|---|
| Server runtime | ASGI3 execution over HTTP/1.1, HTTP/2, HTTP/3, QUIC, and WebSockets | `docs/protocols/`, `examples/` |
| Security | TLS 1.3 controls, ALPN, certificate validation, OCSP, CRL handling | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| Delivery | static files, ETag/conditional handling, range support, content coding, Early Hints, Alt-Svc | `docs/ops/public.md`, `docs/review/conformance/DEPLOYMENT_PROFILES.md` |
| Operations | listeners, workers, reload, metrics, logging, proxy normalization, timeouts and resource controls | `docs/ops/cli.md` |
| Embedding | `run`, `serve`, `serve_import_string`, `EmbeddedServer`, lifecycle hooks | `docs/ops/public.md`, `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` |
| Config | typed config model, config-file loading, env loading, merge from CLI/env/file/defaults | `docs/ops/public.md`, `docs/ops/cli.md` |
| Blessed profiles | generated safe deployment profiles plus profile conformance bundles | `docs/ops/profiles.md`, `docs/conformance/profile_bundles.json` |
| Release checks | release-gate and promotion-target evaluators | `docs/gov/release.md`, `docs/ops/public.md` |
| Current-state and release records | canonical current-state docs plus frozen promoted roots | `docs/review/conformance/state/`, `docs/review/conformance/releases/` |

## Installation and extras

### Base install

```bash
python -m pip install tigrcorn
```

### Certification / development install

```bash
python -m pip install -e ".[certification,dev]"
```

### Optional extras

| Extra | Status | Use it for |
|---|---|---|
| `tls-x509` | supported | package-owned TLS/X.509 validation, certificate handling, and revocation helpers |
| `config-yaml` | supported | `.yaml` / `.yml` config loading |
| `compression` | supported | Brotli content coding and `.br` sidecars |
| `runtime-uvloop` | supported | `--runtime uvloop` on supported platforms |
| `runtime-trio` | declared, not supported | reserved dependency path only |
| `full-featured` | supported | current aggregate optional operator feature surface |
| `certification` | supported | interop and certification tooling |
| `dev` | supported | local development and validation |

### Practical install examples

```bash
# TLS/X.509 validation and certificate-material helpers
python -m pip install -e ".[tls-x509]"

# YAML config support
python -m pip install -e ".[config-yaml]"

# Brotli + precompressed static sidecars
python -m pip install -e ".[compression]"

# uvloop runtime option (non-Windows)
python -m pip install -e ".[runtime-uvloop]"

# current aggregate optional feature surface
python -m pip install -e ".[full-featured]"
```

The authoritative optional dependency reference is `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md`. TLS/X.509 operations rely on the optional `tigrcorn[tls-x509]` extra.

## Protocol and feature map

> **Legend:** `C-RFC` = inside the current certified RFC boundary · `C-OP` = inside the public/operator surface · `O` = outside the current scope

### Core protocol, transport, and delivery

| Category | Surface | Status | Primary docs |
|---|---|---|---|
| HTTP | HTTP/1.1 (`RFC 9112`) | `C-RFC` | `docs/protocols/http1.md` |
| HTTP | HTTP/2 (`RFC 9113`) | `C-RFC` | `docs/protocols/http2.md` |
| HTTP | HTTP/3 (`RFC 9114`) | `C-RFC` | `docs/protocols/http3.md` |
| QUIC | QUIC transport (`RFC 9000`, `RFC 9001`, `RFC 9002`) | `C-RFC` | `docs/protocols/quic.md` |
| WebSocket | RFC 6455 / RFC 8441 / RFC 9220 carriers | `C-RFC` | `docs/protocols/websocket.md` |
| Delivery | CONNECT relay, trailer fields, content coding | `C-RFC` | `docs/review/conformance/DEPLOYMENT_PROFILES.md` |
| Delivery | Conditional requests, range requests, Early Hints, bounded Alt-Svc | `C-RFC` | `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` |
| Security | TLS 1.3, ALPN, X.509, OCSP, CRL | `C-RFC` | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |

### Operator and public API surface

| Category | Surface | Status | Primary docs |
|---|---|---|---|
| CLI | `tigrcorn`, `python -m tigrcorn`, `tigrcorn-interop` | `C-OP` | `docs/ops/cli.md` |
| Config | `build_config`, `build_config_from_namespace`, `build_config_from_sources` | `C-OP` | `docs/ops/public.md` |
| Embedding | `EmbeddedServer`, lifecycle hooks, public lifecycle contract | `C-OP` | `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` |
| Static | `StaticFilesApp`, `mount_static_app`, static route flags | `C-OP` | `docs/ops/public.md` |
| Operations | reload, workers, runtime selection, metrics, logging, proxy normalization | `C-OP` | `docs/ops/cli.md` |
| Release | `evaluate_release_gates`, `evaluate_promotion_target` | `C-OP` | `docs/ops/public.md`, `docs/gov/release.md` |
| Custom transports | pipe / inproc / rawframed / custom | `C-OP` with boundary notes | `docs/protocols/custom-transports.md`, `docs/review/conformance/BOUNDARY_NON_GOALS.md` |

## CLI usage

The main command is `tigrcorn`. The public module entrypoint is `python -m tigrcorn`. The interoperability runner is `tigrcorn-interop`.

For complete operator coverage, use:

- `docs/ops/cli.md`
- `docs/review/conformance/CLI_FLAG_SURFACE.md`
- `docs/review/conformance/cli_flag_surface.json`
- `docs/review/conformance/DEPLOYMENT_PROFILES.md`
- `docs/review/conformance/cli_help.current.txt`
- `docs/review/conformance/tigrcorn_interop_help.current.txt`

### Config precedence

```text
CLI > env > config file > defaults
```

That precedence is implemented by `build_config_from_sources` and documented in `docs/gov/code.md`.

### Common launch patterns

#### Minimal HTTP/1.1 + HTTP/2

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
  --bind 127.0.0.1:8443 \
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
  --static-path-dir-to-file \
  --static-path-index-file index.html \
  --static-path-expires 3600
```

#### CONNECT, trailer, and content-coding policy

```bash
tigrcorn examples.echo_http.app:app \
  --connect-policy allowlist \
  --connect-allow 127.0.0.1:5432 \
  --trailer-policy strict \
  --content-coding-policy allowlist \
  --content-codings br,gzip,deflate
```

#### Automatic Alt-Svc advertisement

```bash
tigrcorn examples.advanced_protocol_delivery.alt_svc_app:app \
  --bind 127.0.0.1:8080 \
  --quic-bind 127.0.0.1:8443 \
  --http 1.1 --http 2 --http 3 \
  --alt-svc-auto \
  --alt-svc-ma 86400 \
  --alt-svc-persist
```

#### Metrics, logging, reload, and workers

```bash
tigrcorn examples.echo_http.app:app \
  --log-level info \
  --structured-log \
  --metrics \
  --metrics-bind 127.0.0.1:9100 \
  --workers 4 \
  --runtime auto \
  --reload \
  --reload-dir ./src
```

#### Unix sockets and custom transports

```bash
tigrcorn examples.echo_http.app:app \
  --transport unix \
  --uds /tmp/tigrcorn.sock
```

```bash
tigrcorn examples.echo_http.app:app \
  --transport pipe \
  --pipe-mode rawframed \
  --protocol rawframed
```

#### Interoperability matrices

```bash
tigrcorn-interop \
  --matrix docs/review/conformance/external_matrix.release.json \
  --output ./artifacts/interop
```

Use `docs/review/conformance/external_matrix.current_release.json` for the current-release bundle contract and `docs/review/conformance/external_matrix.same_stack_replay.json` for same-stack replay coverage.

## Public API and embedding usage

The public import surface is documented in full in `docs/ops/public.md`. Lifecycle guarantees for embedded use live in `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`.

### Public import map

| Import surface | What it is for |
|---|---|
| `tigrcorn.run` | sync convenience entrypoint |
| `tigrcorn.serve` | async entrypoint for an in-memory ASGI app |
| `tigrcorn.serve_import_string` | async entrypoint for an import string |
| `tigrcorn.EmbeddedServer` | explicit embedding and lifecycle control |
| `tigrcorn.StaticFilesApp` | standalone static ASGI app |
| `tigrcorn.static.mount_static_app` | mount static delivery into another ASGI app |
| `tigrcorn.static.normalize_static_route` | normalize public static route input |
| `tigrcorn.config.build_config` | build `ServerConfig` from explicit keyword args |
| `tigrcorn.config.build_config_from_namespace` | convert argparse namespace into config |
| `tigrcorn.config.build_config_from_sources` | merge CLI overrides, config file, and environment |
| `tigrcorn.config.config_to_dict` | inspect or serialize config |
| `tigrcorn.config.load_env_config` | load prefixed environment config |
| `tigrcorn.config.load_config_file` | load TOML / JSON / optional YAML config |
| `tigrcorn.compat.release_gates.evaluate_release_gates` | evaluate release-gate readiness |
| `tigrcorn.compat.release_gates.evaluate_promotion_target` | evaluate promotion-target readiness |
| `tigrcorn.compat.release_gates.assert_release_ready` | fail fast if release gates are not satisfied |
| `tigrcorn.compat.release_gates.assert_promotion_target_ready` | fail fast if promotion target is not satisfied |

### Usage snippets

#### Run from sync code

```python
from tigrcorn import run

run(
    "examples.echo_http.app:app",
    host="127.0.0.1",
    port=8000,
    http_versions=["1.1", "2"],
)
```

#### Run inside an existing event loop

```python
from tigrcorn import serve

async def app(scope, receive, send):
    ...

await serve(app, host="127.0.0.1", port=8000)
```

#### Load an import string inside async code

```python
from tigrcorn import serve_import_string

await serve_import_string(
    "examples.websocket_echo.app:app",
    host="127.0.0.1",
    port=9000,
)
```

#### Embed the server and control lifecycle directly

```python
from tigrcorn import EmbeddedServer
from tigrcorn.config import build_config

config = build_config(host="127.0.0.1", port=0, lifespan="on")

async with EmbeddedServer(app, config) as embedded:
    print(embedded.listeners)
    print(embedded.bound_endpoints())
```

#### Mount static delivery

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

#### Build config from sources

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

#### Evaluate release and promotion state

```python
from tigrcorn.compat.release_gates import evaluate_promotion_target, evaluate_release_gates

release_report = evaluate_release_gates(".")
promotion_report = evaluate_promotion_target(".")

print(release_report.passed)
print(promotion_report.passed)
```

## Current scope

### Current supported runtime surface

| Runtime | Status | Source |
|---|---|---|
| `auto` | supported | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| `asyncio` | supported | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| `uvloop` | supported | `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md` |
| `trio` | reserved dependency path, not supported | `docs/review/conformance/BOUNDARY_NON_GOALS.md` |

### Out-of-boundary families

| Family | Current location |
|---|---|
| Trio as a supported runtime family | `docs/review/conformance/BOUNDARY_NON_GOALS.md` |
| WSGI / ASGI2 / RSGI compatibility layers | `docs/review/conformance/BOUNDARY_NON_GOALS.md` |
| Parser pluggability | `docs/review/conformance/BOUNDARY_NON_GOALS.md` |
| WebSocket engine pluggability | `docs/review/conformance/BOUNDARY_NON_GOALS.md` |
| RFC 9111 caching | `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` |
| RFC 9530 digest fields | `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` |
| RFC 9421 message signatures | `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` |
| JOSE / COSE layers | `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` |

## Status at a glance

| Topic | Current source of truth |
|---|---|
| Repo line | `0.3.9` in `pyproject.toml` and `src/tigrcorn/version.py` |
| Current state | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` |
| Current-state chain | `docs/review/conformance/CURRENT_STATE_CHAIN.md`, `docs/review/conformance/current_state_chain.current.json` |
| Authoritative boundary | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| Strict profile | `docs/review/conformance/STRICT_PROFILE_TARGET.md` |
| Canonical promoted root | `docs/review/conformance/releases/0.3.9/release-0.3.9/` |
| Operator docs | `docs/ops/README.md`, `docs/ops/cli.md`, `docs/ops/public.md` |
| Lifecycle and embedding contract | `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` |
| Optional dependency truth | `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md`, `docs/review/conformance/optional_dependency_surface.current.json` |
| External evidence inputs | `external_matrix.same_stack_replay.json`, `external_matrix.release.json`, `external_matrix.current_release.json` |
| Planning and promotion checkpoints | `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`, `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md` |

### Current repository claim

Under `docs/review/conformance/CERTIFICATION_BOUNDARY.md`, the package is **certifiably fully RFC compliant under the authoritative certification boundary**. The canonical promoted root at `docs/review/conformance/releases/0.3.9/release-0.3.9/` is **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.[^boundary]

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
- `docs/review/conformance/RELEASE_GATE_STATUS.md`
- `docs/review/conformance/STRICT_PROFILE_TARGET.md`
- `docs/review/conformance/FLAG_CERTIFICATION_TARGET.md`
- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`

## Where to look

| If you are… | Start here | Then go to |
|---|---|---|
| Launching Tigrcorn as an operator | `docs/ops/cli.md` | `docs/review/conformance/DEPLOYMENT_PROFILES.md` |
| Embedding Tigrcorn in another process | `docs/ops/public.md` | `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` |
| Working on static or delivery behavior | `docs/ops/public.md` | `examples/http_entity_static/app.py` |
| Reviewing current repository truth | `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` | `docs/review/conformance/current_state_chain.current.json` |
| Reviewing the promoted release root | `docs/review/conformance/releases/0.3.9/release-0.3.9/` | `RELEASE_NOTES_0.3.9.md` |
| Reviewing the boundary or current scope | `docs/review/conformance/CERTIFICATION_BOUNDARY.md` | `docs/review/conformance/BOUNDARY_NON_GOALS.md` |
| Comparing Tigrcorn with peer servers | `docs/comp/rfc.md` | `docs/comp/cli.md`, `docs/comp/ops.md`, `docs/comp/oob.md` |
| Writing or maintaining docs | `docs/gov/authoring.md` | `CONTRIBUTING.md`, `docs/gov/tree.md`, `docs/gov/mut.md` |
| Working on release or promotion | `docs/gov/release.md` | `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md` |
| Acting as an agent or automation | `AGENTS.md` | `tools/govchk.py` |

## Governance and maintainer workflow

Maintainer and authoring guidance lives in:

- `docs/gov/authoring.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `docs/gov/release.md`

The short version:

1. update code and tests together
2. update machine-readable truth together with human docs
3. keep current-state pointers current
4. create new preserved artifacts for promotion-relevant changes instead of editing a frozen release root

Useful governance checks:

```bash
python tools/govchk.py state README.md
python tools/govchk.py state docs/review/conformance/releases/0.3.9
python tools/govchk.py scan
```

Repository cleanliness is governed by `MUT.json`, `docs/gov/tree.md`, `docs/gov/mut.md`, `docs/gov/code.md`, and ADR `.ssot/adr/ADR-1005-doc-gov.md`.

## Current-state and historical planning

For current repository truth, start with:

- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/state/README.md`
- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`

For planning and promotion history, use:

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

These files explain how the repository got to the current promoted state without replacing the canonical current-state pointer.

## Certification environment freeze

The certification environment freeze documents the install contract and runtime prerequisites for the strict release workflow.

Start with:

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

The freeze distinguishes the authoritative release-workflow contract from the observed local editing environment.[^freeze]

## Contributing, conduct, and community norms

- `CONTRIBUTING.md` explains how to make changes without drifting from the boundary, tests, current-state chain, or release evidence.
- `CODE_OF_CONDUCT.md` defines participation expectations and reporting guidance.
- `docs/gov/authoring.md` explains how maintainers and authors should update the repository without creating truth conflicts.
- `docs/gov/tree.md` and `docs/gov/mut.md` explain where new files belong and which trees are frozen.

## Footnotes

[^boundary]: Certification language in this repository is scoped by `docs/review/conformance/CERTIFICATION_BOUNDARY.md` and `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`. The current package claim and the promoted-root claim are related, but they are not the same statement.

[^freeze]: The freeze preserves the release-workflow contract even when the local working environment is missing a certification dependency such as `aioquic`.
