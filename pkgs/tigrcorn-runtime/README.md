<div align="center">
<h1>tigrcorn-runtime</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Server runner, app loading, lifecycle hooks, workers, reload, and embedded runtime for the Tigrcorn ASGI3 web server.</strong></p>

<a href="https://pypi.org/project/tigrcorn-runtime/"><img alt="PyPI version for tigrcorn-runtime" src="https://img.shields.io/pypi/v/tigrcorn-runtime?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-runtime/"><img alt="tigrcorn-runtime package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-runtime"><img alt="Downloads for tigrcorn-runtime" src="https://static.pepy.tech/badge/tigrcorn-runtime"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-runtime/README.md"><img alt="Hits for tigrcorn-runtime README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-runtime/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-runtime/"><img alt="runtime role package" src="https://img.shields.io/badge/role-runtime-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-runtime
```

```bash
pip install tigrcorn-runtime
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-runtime</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-runtime</code> owns server runner, app loading, bootstrap, signals, shutdown, workers, embedding, and cli. Its import package is <code>tigrcorn_runtime</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-config, tigrcorn-asgi, tigrcorn-transports, tigrcorn-protocols, tigrcorn-security.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-runtime</code> when you want the runtime layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_runtime</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for server runner, app loading, bootstrap, signals, shutdown, workers, embedding, and cli in the Tigrcorn package graph.

### What should be imported from the runtime package first?

Start with run, serve, or serve_import_string when you need the packaged server entrypoints, embedded runtime orchestration, bootstrap flow, or worker lifecycle management.

## Features

- Owns server runner, app loading, bootstrap, signals, shutdown, workers, embedding, and cli inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_runtime</code> import surface for named public helpers and entrypoints.
- Declared runtime dependencies: tigrcorn-core, tigrcorn-config, tigrcorn-asgi, tigrcorn-transports, tigrcorn-protocols, tigrcorn-security.
- Optional dependency surface: uvloop, trio.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-runtime</code> when you need runtime-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
from tigrcorn_runtime import run

print(run.__name__)
```

Namespace discovery starts with `import tigrcorn_runtime`.

The package exposes its supported public surface through the <code>tigrcorn_runtime</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/)
- [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/)
- [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/)
- [tigrcorn-security](https://pypi.org/project/tigrcorn-security/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)
- [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-quic-cc](https://pypi.org/project/tigrcorn-quic-cc/) | [tigrcorn-quic-cc-reno](https://pypi.org/project/tigrcorn-quic-cc-reno/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Use this package when you need the packaged server entrypoints or embedded runtime orchestration.
- Keep worker, reload, and bootstrap behavior documented here before surfacing it at the repo root.
- Use config, protocol, transport, and security packages as inputs instead of re-owning those concerns in runtime code.

## License

Apache-2.0
