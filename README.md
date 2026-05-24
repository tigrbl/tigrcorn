<div align="center">
<h1>Tigrcorn</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="220"
/>

<p><strong>ASGI3 Python web server with built-in HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, WebTransport, TLS, static delivery, and certification tooling.</strong></p>

<a href="https://pypi.org/project/tigrcorn/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/tigrcorn?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn/"><img alt="tigrcorn package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn"><img alt="Downloads for tigrcorn" src="https://static.pepy.tech/badge/tigrcorn"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/README.md"><img alt="Hits for tigrcorn README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://www.npmjs.com/package/@tigrcorn/wt-peer-probes"><img alt="npm package for webtransport probes" src="https://img.shields.io/badge/npm-wt--peer--probes-cb3837"></a>
<a href="docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md"><img alt="runtime auto, asyncio, uvloop documented" src="https://img.shields.io/badge/runtime-auto%20%7C%20asyncio%20%7C%20uvloop-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## What It Is

Tigrcorn is an ASGI3 Python web server and package family for teams that want modern protocol support, explicit operator controls, and a public runtime surface that matches the shipped implementation. The repo publishes a top-level `tigrcorn` distribution, 13 split PyPI packages under `pkgs/`, and one npm package for browser-side WebTransport peer probes under `packages/wt-peer-probes`.

The current published package surface covers HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, WebTransport-adjacent probe rails, TLS and X.509 handling, typed configuration, static delivery, observability, compatibility shims, runtime orchestration, and certification tooling. There are currently no Rust crate packages in this repository.

## Why Use Tigrcorn?

Use Tigrcorn when you need a Python ASGI server with first-party HTTP/3 and QUIC work, a documented split-package architecture, and repo-local governance around what is claimed, tested, and released. It is aimed at operators, application hosts, and maintainers who want protocol capability, importable runtime entrypoints, and SSOT-backed certification surfaces in the same codebase.

## FAQ

### What packages does this repo publish?

The repo publishes the aggregate `tigrcorn` package, 13 PyPI subpackages in `pkgs/*`, and the npm package `@tigrcorn/wt-peer-probes` for browser-side WebTransport validation.

### Which package should most Python users install first?

Start with `tigrcorn` when you want the full server distribution. Install one of the split packages directly when you want only a specific boundary such as config, HTTP helpers, runtime, certification, or static delivery.

### Does this repo include crates?

No. This repository currently ships Python packages and one npm package, but no Rust crates.

### Where is the authoritative scope and release truth?

The authoritative machine-readable source is [`.ssot/registry.json`](https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json). Maintainer-facing release and conformance material lives under [`docs/review/conformance/`](https://github.com/Tigrbl/tigrcorn/tree/master/docs/review/conformance).

## Features

- Runs ASGI3 applications over HTTP/1.1, HTTP/2, HTTP/3, QUIC, and WebSocket surfaces.
- Ships typed config builders, public runtime entrypoints, static delivery helpers, and operator-facing CLI rails.
- Splits the server into installable PyPI package boundaries so downstream users can depend on narrower surfaces.
- Publishes certification and promotion helpers for release-gate and evidence-oriented workflows.
- Includes an npm WebTransport peer probe package for browser interoperability and live-endpoint checks.
- Keeps scope, package boundaries, and release claims tied to SSOT and repo-local conformance artifacts.

## Installation

### Python

```bash
python -m pip install tigrcorn
```

### Python with certification and development extras

```bash
python -m pip install -e ".[certification,dev]"
```

### npm peer probe package

```bash
npm install @tigrcorn/wt-peer-probes
```

## Quick Start

### Run an HTTP server

```bash
tigrcorn examples.echo_http.app:app --host 127.0.0.1 --port 8000
```

### Run HTTP/3 and QUIC

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

### Run the browser peer probe matrix

```bash
cd packages/wt-peer-probes
npm run test:peer-api
```

## Package Map

### PyPI packages

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

### npm packages

| Package | Owns |
| --- | --- |
| [`@tigrcorn/wt-peer-probes`](https://www.npmjs.com/package/@tigrcorn/wt-peer-probes) | browser-side WebTransport probe execution and Playwright peer validation |

## Usage by Workflow

### Configure and run from Python

```python
from tigrcorn import run
from tigrcorn.config import build_config_from_sources, config_to_dict

config = build_config_from_sources(
    config_path="./tigrcorn.toml",
    env_prefix="TIGRCORN",
)

run("examples.echo_http.app:app", **config_to_dict(config))
```

### Serve from an existing event loop

```python
from tigrcorn import serve

async def app(scope, receive, send):
    ...

await serve(app, host="127.0.0.1", port=8000)
```

### Evaluate release readiness

```python
from tigrcorn.compat.release_gates import evaluate_release_gates

report = evaluate_release_gates(".")
print(report.passed)
```

## Related Surfaces

- [docs/ops/public.md](docs/ops/public.md)
- [docs/ops/cli.md](docs/ops/cli.md)
- [docs/LIFECYCLE_AND_EMBEDDED_SERVER.md](docs/LIFECYCLE_AND_EMBEDDED_SERVER.md)
- [docs/review/conformance/CERTIFICATION_BOUNDARY.md](docs/review/conformance/CERTIFICATION_BOUNDARY.md)
- [docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md](docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md)
- [packages/wt-peer-probes/README.md](packages/wt-peer-probes/README.md)

## More Documentation

- [docs/ops/README.md](docs/ops/README.md)
- [docs/protocols/](docs/protocols/)
- [docs/gov/release.md](docs/gov/release.md)
- [docs/gov/authoring.md](docs/gov/authoring.md)
- [docs/review/conformance/](docs/review/conformance/)
- [.codex/AGENTS.md](.codex/AGENTS.md)

## Best Practices

- Start with the aggregate `tigrcorn` package unless you have a clear reason to depend on a narrower package boundary.
- Keep protocol, operator, and release claims aligned with `.ssot/registry.json` and the corresponding conformance docs.
- Use split packages to document ownership boundaries rather than re-exporting unrelated behavior into one surface.
- Change browser probe contracts together with the Python WebTransport endpoint behavior and Playwright evidence.

## License

Apache-2.0
