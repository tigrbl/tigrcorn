<div align="center">
<h1>tigrcorn-observability</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Logging, metrics, tracing, DoS warning events, and release-evidence metadata for the Tigrcorn Python web server.</strong></p>

<a href="https://pypi.org/project/tigrcorn-observability/"><img alt="PyPI version for tigrcorn-observability" src="https://img.shields.io/pypi/v/tigrcorn-observability?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-observability/"><img alt="tigrcorn-observability package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-observability"><img alt="Downloads for tigrcorn-observability" src="https://static.pepy.tech/badge/tigrcorn-observability"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-observability/README.md"><img alt="Hits for tigrcorn-observability README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-observability/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-observability/"><img alt="observability role package" src="https://img.shields.io/badge/role-observability-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-observability
```

```bash
pip install tigrcorn-observability
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-observability</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-observability</code> owns logging, metrics, tracing, and evidence metadata export. Its import package is <code>tigrcorn_observability</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-config.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-observability</code> when you want the observability layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_observability</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for logging, metrics, tracing, and evidence metadata export in the Tigrcorn package graph.

### What observability outputs does this package support?

It owns logging, metrics, tracing, DoS warning events, and evidence metadata export surfaces that can be consumed by certification, runtime, and operator workflows.

## Features

- Owns logging, metrics, tracing, and evidence metadata export inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_observability</code> import surface for module-oriented public surfaces.
- Declared runtime dependencies: tigrcorn-core, tigrcorn-config.
- Optional dependency surface: none.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-observability</code> when you need observability-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
import tigrcorn_observability

print(tigrcorn_observability.__name__)
```

The package exposes its supported public surface through the <code>tigrcorn_observability</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Route new logging, metrics, tracing, and evidence metadata work through this package first.
- Keep operator-facing observability changes aligned with release evidence and certification consumers.
- Avoid mixing observability transport or storage policy into this package unless it is part of the public contract.

## License

Apache-2.0
