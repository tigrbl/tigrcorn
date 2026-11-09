<div align="center">

<h1>Tigrcorn</h1>

<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="220"
/>

> ASGI3 server with built-in HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, TLS, static delivery, and release validation.

---
</div>

<p align="center"><a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>


<p align="center"><strong>Release status</strong><br>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pyproject.toml"><img alt="repo line 0.3.16.dev5" src="https://img.shields.io/badge/repo_line-0.3.16.dev5-2f7ed8"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md"><img alt="current state canonical" src="https://img.shields.io/badge/current_state-canonical-0969da"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md"><img alt="authoritative boundary green" src="https://img.shields.io/badge/authoritative_boundary-green-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/STRICT_PROFILE_TARGET.md"><img alt="strict profile green" src="https://img.shields.io/badge/strict_profile-green-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/tree/master/docs/review/conformance/releases/0.3.9/release-0.3.9"><img alt="promotion green" src="https://img.shields.io/badge/promotion-green-1f883d"></a>
</p>

<p align="center"><strong>Package</strong><br>
<a href="https://pypi.org/project/tigrcorn/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/tigrcorn?label=PyPI"></a>
<a href="https://pepy.tech/project/tigrcorn"><img alt="Downloads for tigrcorn" src="https://static.pepy.tech/badge/tigrcorn"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/README.md"><img alt="Hits for tigrcorn README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/README.md.svg?label=hits"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/LICENSE"><img alt="license Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md"><img alt="runtime auto supported" src="https://img.shields.io/badge/runtime-auto-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md"><img alt="runtime asyncio supported" src="https://img.shields.io/badge/runtime-asyncio-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md"><img alt="runtime uvloop supported" src="https://img.shields.io/badge/runtime-uvloop-0a7f5a"></a>
</p>

<p align="center"><strong>Protocol status</strong><br>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/http1.md"><img alt="HTTP/1.1 C-RFC" src="https://img.shields.io/badge/HTTP%2F1.1-C--RFC-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/http2.md"><img alt="HTTP/2 C-RFC" src="https://img.shields.io/badge/HTTP%2F2-C--RFC-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/http3.md"><img alt="HTTP/3 C-RFC" src="https://img.shields.io/badge/HTTP%2F3-C--RFC-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/quic.md"><img alt="QUIC C-RFC" src="https://img.shields.io/badge/QUIC-C--RFC-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/websocket.md"><img alt="WebSocket C-RFC" src="https://img.shields.io/badge/WebSocket-C--RFC-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/websocket.md"><img alt="RFC 8441 C-RFC" src="https://img.shields.io/badge/RFC8441-C--RFC-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/websocket.md"><img alt="RFC 9220 C-RFC" src="https://img.shields.io/badge/RFC9220-C--RFC-1f883d"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md"><img alt="TLS 1.3 X.509 OCSP C-RFC" src="https://img.shields.io/badge/TLS1.3_X.509_OCSP-C--RFC-1f883d"></a>
</p>

<p align="center"><strong>Operator and API surface status</strong><br>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md"><img alt="CLI C-OP" src="https://img.shields.io/badge/CLI-C--OP-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md"><img alt="EmbeddedServer C-OP" src="https://img.shields.io/badge/EmbeddedServer-C--OP-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md"><img alt="Lifecycle hooks C-OP" src="https://img.shields.io/badge/Lifecycle_hooks-C--OP-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md"><img alt="StaticFilesApp C-OP" src="https://img.shields.io/badge/StaticFilesApp-C--OP-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md"><img alt="Workers and reload C-OP" src="https://img.shields.io/badge/Workers_reload-C--OP-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md"><img alt="Metrics and logging C-OP" src="https://img.shields.io/badge/Metrics_logging-C--OP-0a7f5a"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md"><img alt="Release gates C-OP" src="https://img.shields.io/badge/Release_gates-C--OP-0a7f5a"></a>
</p>


---

Tigrcorn is an ASGI3 server for Python teams building APIs, edge services, internal platforms, and protocol-heavy applications that need modern transport support without giving up operational control. It implements HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSockets, TLS handling, static delivery, and release checks inside the project, with operator docs and current-state material kept alongside the code.

Most users should start with **Quick start**, **Protocol and feature map**, and **CLI usage**. Maintainers should use the SSOT, governance, and conformance links when changing claimed support, release boundaries, or certification evidence.


## Table of contents

- [Legend](#legend)
- [Choose your path](#choose-your-path)
- [Quick start](#quick-start)
- [Why teams pick Tigrcorn](#why-teams-pick-tigrcorn)
- [What Tigrcorn provides](#what-tigrcorn-provides)
- [Published packages](#published-packages)
- [Installation and extras](#installation-and-extras)
- [Protocol and feature map](#protocol-and-feature-map)
- [CLI usage](#cli-usage)
- [Public API and embedding usage](#public-api-and-embedding-usage)
- [Current scope](#current-scope)
- [Status at a glance](#status-at-a-glance)
- [Validation and promotion](#validation-and-promotion)
- [Where to look](#where-to-look)
- [Contributing, conduct, and community norms](#contributing-conduct-and-community-norms)
- [Footnotes](#footnotes)

## Legend

Use this legend for the badges, status tables, and scope markers in this README.

| Marker | Meaning |
|---|---|
| `C-RFC` | included in Tigrcorn's current certified RFC boundary |
| `C-OP` | included in Tigrcorn's current public operator/API surface |
| `OOB` | outside Tigrcorn's current documented boundary and shipped surface |
| `green` | the referenced repo contract or evaluation target is currently passing |
| `canonical` | the referenced document is the current mutable source of truth |
| `repo_line` | the active repository release line represented by this checkout |
| `runtime-auto`, `runtime-asyncio`, `runtime-uvloop` | documented runtime modes in the current public surface |

The top badge groups use plain language labels where possible. The protocol and feature tables use `C-RFC`, `C-OP`, and `OOB` as compact scope markers.

## Choose your path

| Goal | Start with | Then use |
|---|---|---|
| Run Tigrcorn as an ASGI server | [Quick start](#quick-start) | [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md), [deployment profiles](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/profiles.md) |
| Configure production behavior | [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md) | [defaults](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/defaults.md), [observability](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/observability.md), [policies](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/policies.md) |
| Build on Tigrcorn from Python | [Public API and embedding usage](#public-api-and-embedding-usage) | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md), [lifecycle and embedded server guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md) |
| Understand protocol and feature support | [Protocol and feature map](#protocol-and-feature-map) | [protocol docs](https://github.com/tigrbl/tigrcorn/tree/master/docs/protocols/), [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md), [`.ssot/registry.json`](https://github.com/tigrbl/tigrcorn/blob/master/.ssot/registry.json) |
| Review release and conformance status | [Status at a glance](#status-at-a-glance) | [Validation and promotion](#validation-and-promotion), [conformance docs](https://github.com/tigrbl/tigrcorn/tree/master/docs/review/conformance/) |

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

For complete operator recipes, use [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md). For public imports and lifecycle details, use [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md) and [lifecycle and embedded server guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md).
For the blessed safe deployment profiles, use [deployment profiles](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/profiles.md) and the [packaged profile artifacts](https://github.com/tigrbl/tigrcorn/tree/master/src/tigrcorn/profiles/).

## Why teams pick Tigrcorn

- **Modern protocol stack in the server itself.** HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSockets, TLS 1.3, ALPN, X.509 validation, OCSP, and CRL handling are first-class documented surfaces.
- **Operator features that matter in deployment.** Listener binding, TLS and QUIC controls, workers, reload, structured logging, metrics, proxy normalization, content-coding policy, CONNECT policy, Early Hints, Alt-Svc, and static delivery are part of the public surface.
- **A public Python API for applications and hosts.** `run`, `serve`, `serve_import_string`, `EmbeddedServer`, `StaticFilesApp`, and the config helpers are documented as importable entrypoints.
- **Static delivery and entity semantics built into the package.** Static mounting, precompressed sidecars, conditional requests, range requests, and response-path helpers are available without a separate static server wrapper.
- **Release and promotion checks in the repo.** `evaluate_release_gates` and `evaluate_promotion_target` are shipped APIs, and the repo preserves current-state and promoted-release material under [conformance docs](https://github.com/tigrbl/tigrcorn/tree/master/docs/review/conformance/).

## What Tigrcorn provides

| Area | What you get | Primary docs |
|---|---|---|
| Server runtime | ASGI3 execution over HTTP/1.1, HTTP/2, HTTP/3, QUIC, and WebSockets | [protocol docs](https://github.com/tigrbl/tigrcorn/tree/master/docs/protocols/), [examples](https://github.com/tigrbl/tigrcorn/tree/master/examples/) |
| Security | TLS 1.3 controls, ALPN, certificate validation, OCSP, CRL handling | [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md) |
| Delivery | static files, ETag/conditional handling, range support, content coding, Early Hints, Alt-Svc | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md), [deployment profiles reference](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/DEPLOYMENT_PROFILES.md) |
| Operations | listeners, workers, reload, metrics, logging, proxy normalization, timeouts and resource controls | [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md) |
| Embedding | `run`, `serve`, `serve_import_string`, `EmbeddedServer`, lifecycle hooks | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md), [lifecycle and embedded server guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md) |
| Config | typed config model, config-file loading, env loading, merge from CLI/env/file/defaults | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md), [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md) |
| Blessed profiles | generated safe deployment profiles plus profile conformance bundles | [deployment profiles](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/profiles.md), [profile bundles JSON](https://github.com/tigrbl/tigrcorn/blob/master/docs/conformance/profile_bundles.json) |
| Release checks | release-gate and promotion-target evaluators | [release workflow guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/release.md), [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md) |
| Current-state and release records | canonical current-state docs plus frozen promoted roots | [state docs index](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/state/README.md), [release roots](https://github.com/tigrbl/tigrcorn/tree/master/docs/review/conformance/releases/) |

## Published packages

### Python package family

| Package | Owns |
| --- | --- |
| [`tigrcorn`](https://pypi.org/project/tigrcorn/) | aggregate distribution and compatibility umbrella |
| [`tigrcorn-core`](https://pypi.org/project/tigrcorn-core/) | constants, errors, types, and shared utils |
| [`tigrcorn-config`](https://pypi.org/project/tigrcorn-config/) | config models, validation, profiles, env and file loading |
| [`tigrcorn-http`](https://pypi.org/project/tigrcorn-http/) | entity tags, headers, conditional requests, ranges, and HTTP helpers |
| [`tigrcorn-asgi`](https://pypi.org/project/tigrcorn-asgi/) | ASGI send and receive adapters and response materialization |
| [`tigrcorn-contract`](https://pypi.org/project/tigrcorn-contract/) | event ordering, scope validation, and ASGI contract helpers |
| [`tigrcorn-transports`](https://pypi.org/project/tigrcorn-transports/) | TCP, UDP, Unix, pipe, and transport machinery |
| [`tigrcorn-security`](https://pypi.org/project/tigrcorn-security/) | TLS, ALPN, X.509, OCSP, and CRL handling |
| [`tigrcorn-protocols`](https://pypi.org/project/tigrcorn-protocols/) | HTTP/1.1, HTTP/2, HTTP/3, QUIC, sessions, streams, and schedulers |
| [`tigrcorn-static`](https://pypi.org/project/tigrcorn-static/) | static delivery and route mounting |
| [`tigrcorn-observability`](https://pypi.org/project/tigrcorn-observability/) | metrics and logging surfaces |
| [`tigrcorn-runtime`](https://pypi.org/project/tigrcorn-runtime/) | app loading, runner, workers, reload, embedding, and CLI |
| [`tigrcorn-compat`](https://pypi.org/project/tigrcorn-compat/) | root-namespace shims and promotion helpers |
| [`tigrcorn-certification`](https://pypi.org/project/tigrcorn-certification/) | release gates, strict promotion checks, and external evidence rails |

### npm package

| Package | Owns |
| --- | --- |
| [`@tigrcorn/wt-peer-probes`](https://www.npmjs.com/package/@tigrcorn/wt-peer-probes) | browser-side WebTransport probe execution and Playwright peer validation |

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

The authoritative optional dependency reference is [optional dependency surface](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md). TLS/X.509 operations rely on the optional `tigrcorn[tls-x509]` extra.

## Protocol and feature map

This section is a public support snapshot. It keeps protocol and feature details visible in the README while making Tigrcorn's depth, feature surface, and domain coverage explicit. Use `C-RFC` for current certified protocol claims, `C-OP` for current operator/API surfaces, and `OOB` for intentionally out-of-boundary behavior.

> **Legend:** `C-RFC` = inside the current certified RFC boundary Â· `C-OP` = inside the public/operator surface Â· `OOB` = outside the current scope

### Core protocol, transport, and delivery

| Category | Surface | Status | Primary docs |
|---|---|---|---|
| HTTP | HTTP/1.1 (`RFC 9112`) | `C-RFC` | [HTTP/1.1 docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/http1.md) |
| HTTP | HTTP/2 (`RFC 9113`) | `C-RFC` | [HTTP/2 docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/http2.md) |
| HTTP | HTTP/3 (`RFC 9114`) | `C-RFC` | [HTTP/3 docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/http3.md) |
| QUIC | QUIC transport (`RFC 9000`, `RFC 9001`, `RFC 9002`) | `C-RFC` | [QUIC docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/quic.md) |
| WebSocket | RFC 6455 / RFC 8441 / RFC 9220 carriers | `C-RFC` | [WebSocket docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/websocket.md) |
| Delivery | CONNECT relay, trailer fields, content coding | `C-RFC` | [deployment profiles reference](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/DEPLOYMENT_PROFILES.md) |
| Delivery | Conditional requests, range requests, Early Hints, bounded Alt-Svc | `C-RFC` | [RFC applicability and competitor status](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md) |
| Security | TLS 1.3, ALPN, X.509, OCSP, CRL | `C-RFC` | [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md) |

### Operator and public API surface

| Category | Surface | Status | Primary docs |
|---|---|---|---|
| CLI | `tigrcorn`, `python -m tigrcorn`, `tigrcorn-interop` | `C-OP` | [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md) |
| Config | `build_config`, `build_config_from_namespace`, `build_config_from_sources` | `C-OP` | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md) |
| Embedding | `EmbeddedServer`, lifecycle hooks, public lifecycle contract | `C-OP` | [lifecycle and embedded server guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md) |
| Static | `StaticFilesApp`, `mount_static_app`, static route flags | `C-OP` | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md) |
| Operations | reload, workers, runtime selection, metrics, logging, proxy normalization | `C-OP` | [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md) |
| Release | `evaluate_release_gates`, `evaluate_promotion_target` | `C-OP` | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md), [release workflow guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/release.md) |
| Custom transports | pipe / inproc / rawframed / custom | `C-OP` with boundary notes | [custom transport docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/protocols/custom-transports.md), [boundary non-goals](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/BOUNDARY_NON_GOALS.md) |

## CLI usage

The main command is `tigrcorn`. The public module entrypoint is `python -m tigrcorn`. The interoperability runner is `tigrcorn-interop`.

For complete operator coverage, use:

- [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md)
- [CLI flag surface](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CLI_FLAG_SURFACE.md)
- [CLI flag surface JSON](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/cli_flag_surface.json)
- [deployment profiles reference](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/DEPLOYMENT_PROFILES.md)
- [current CLI help snapshot](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/cli_help.current.txt)
- [current interop help snapshot](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/tigrcorn_interop_help.current.txt)

### Config precedence

```text
CLI > env > config file > defaults
```

That precedence is implemented by `build_config_from_sources` and documented in [code governance](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/code.md).

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

Use [current-release external matrix](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/external_matrix.current_release.json) for the current-release bundle contract and [same-stack replay matrix](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/external_matrix.same_stack_replay.json) for same-stack replay coverage.

## Public API and embedding usage

The public import surface is documented in full in [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md). Lifecycle guarantees for embedded use live in [lifecycle and embedded server guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md).

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
| `auto` | supported | [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md) |
| `asyncio` | supported | [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md) |
| `uvloop` | supported | [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md), [optional dependency surface](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md) |
| `trio` | reserved dependency path, not supported | [boundary non-goals](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/BOUNDARY_NON_GOALS.md) |

### Out-of-boundary families

| Family | Current location |
|---|---|
| Trio as a supported runtime family | [boundary non-goals](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/BOUNDARY_NON_GOALS.md) |
| WSGI / ASGI2 / RSGI compatibility layers | [boundary non-goals](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/BOUNDARY_NON_GOALS.md) |
| Parser pluggability | [boundary non-goals](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/BOUNDARY_NON_GOALS.md) |
| WebSocket engine pluggability | [boundary non-goals](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/BOUNDARY_NON_GOALS.md) |
| RFC 9111 caching | [RFC applicability and competitor status](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md) |
| RFC 9530 digest fields | [RFC applicability and competitor status](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md) |
| RFC 9421 message signatures | [RFC applicability and competitor status](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md) |
| JOSE / COSE layers | [RFC applicability and competitor status](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md) |

## Status at a glance

| Topic | Current source of truth |
|---|---|
| Repo line | `0.3.16.dev5` in `pyproject.toml` and the shipped facade import surface |
| Current state | [current repository state](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md) |
| Canonical machine-readable registry | [`.ssot/registry.json`](https://github.com/tigrbl/tigrcorn/blob/master/.ssot/registry.json) |
| Current-state chain | [current-state chain](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CURRENT_STATE_CHAIN.md), [current-state chain JSON](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/current_state_chain.current.json) |
| Authoritative boundary | [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md) |
| Strict profile | [strict profile target](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/STRICT_PROFILE_TARGET.md) |
| Canonical promoted root | [canonical promoted root](https://github.com/tigrbl/tigrcorn/tree/master/docs/review/conformance/releases/0.3.9/release-0.3.9/) |
| Operator docs | [operator docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/README.md), [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md), [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md) |
| Lifecycle and embedding contract | [lifecycle and embedded server guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md) |
| Optional dependency truth | [optional dependency surface](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md), [optional dependency surface JSON](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/optional_dependency_surface.current.json) |
| External evidence inputs | [same-stack replay matrix](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/external_matrix.same_stack_replay.json), [release external matrix](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/external_matrix.release.json), [current-release external matrix](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/external_matrix.current_release.json) |
| Planning and promotion checkpoints | [Release certification implementation plan](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/RELEASE_IMPLEMENTATION_PLAN.md), [Promotion contract promotion contract freeze](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/PROMOTION_CONTRACT_PROMOTION_CONTRACT_FREEZE.md) |

### Current repository claim

Under [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md), the package is **certifiably fully RFC compliant under the authoritative certification boundary**. The canonical promoted root at [canonical promoted root](https://github.com/tigrbl/tigrcorn/tree/master/docs/review/conformance/releases/0.3.9/release-0.3.9/) is **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.[^boundary]

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

- [release workflow guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/release.md)
- [release gate status](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/RELEASE_GATE_STATUS.md)
- [strict profile target](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/STRICT_PROFILE_TARGET.md)
- [flag certification target](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/FLAG_CERTIFICATION_TARGET.md)
- [Promotion contract promotion contract freeze](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/PROMOTION_CONTRACT_PROMOTION_CONTRACT_FREEZE.md)

## Where to look

| If you are... | Start here | Then go to |
|---|---|---|
| Launching Tigrcorn as an operator | [CLI docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/cli.md) | [deployment profiles reference](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/DEPLOYMENT_PROFILES.md) |
| Embedding Tigrcorn in another process | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md) | [lifecycle and embedded server guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/LIFECYCLE_AND_EMBEDDED_SERVER.md) |
| Working on static or delivery behavior | [public API docs](https://github.com/tigrbl/tigrcorn/blob/master/docs/ops/public.md) | [static delivery example](https://github.com/tigrbl/tigrcorn/blob/master/examples/http_entity_static/app.py) |
| Reviewing current repository truth | [current repository state](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md) | [current-state chain JSON](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/current_state_chain.current.json) |
| Reviewing the promoted release root | [canonical promoted root](https://github.com/tigrbl/tigrcorn/tree/master/docs/review/conformance/releases/0.3.9/release-0.3.9/) | [release notes 0.3.9](https://github.com/tigrbl/tigrcorn/blob/master/docs/release-notes/RELEASE_NOTES_0.3.9.md) |
| Reviewing the boundary or current scope | [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md) | [boundary non-goals](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/BOUNDARY_NON_GOALS.md) |
| Comparing Tigrcorn with peer servers | [RFC comparison](https://github.com/tigrbl/tigrcorn/blob/master/docs/comp/rfc.md) | [CLI comparison](https://github.com/tigrbl/tigrcorn/blob/master/docs/comp/cli.md), [operations comparison](https://github.com/tigrbl/tigrcorn/blob/master/docs/comp/ops.md), [out-of-bound comparison](https://github.com/tigrbl/tigrcorn/blob/master/docs/comp/oob.md) |
| Writing or maintaining docs | [authoring guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/authoring.md) | [`CONTRIBUTING.md`](https://github.com/tigrbl/tigrcorn/blob/master/CONTRIBUTING.md), [tree rules](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/tree.md), [mutability rules](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/mut.md) |
| Working on release or promotion | [release workflow guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/release.md) | [Promotion contract promotion contract freeze](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/PROMOTION_CONTRACT_PROMOTION_CONTRACT_FREEZE.md) |

## Contributing, conduct, and community norms

- [`CONTRIBUTING.md`](https://github.com/tigrbl/tigrcorn/blob/master/CONTRIBUTING.md) explains how to make changes without drifting from the boundary, tests, current-state chain, or release evidence.
- [`CODE_OF_CONDUCT.md`](https://github.com/tigrbl/tigrcorn/blob/master/CODE_OF_CONDUCT.md) defines participation expectations and reporting guidance.
- [authoring guide](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/authoring.md) explains how maintainers and authors should update the repository without creating truth conflicts.
- [tree rules](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/tree.md) and [mutability rules](https://github.com/tigrbl/tigrcorn/blob/master/docs/gov/mut.md) explain where new files belong and which trees are frozen.

## Footnotes

[^boundary]: Certification language in this repository is scoped by [certification boundary](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/CERTIFICATION_BOUNDARY.md) and [current repository state](https://github.com/tigrbl/tigrcorn/blob/master/docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md). The current package claim and the promoted-root claim are related, but they are not the same statement.

[^freeze]: The freeze preserves the release-workflow contract even when the local working environment is missing a certification dependency such as `aioquic`.
