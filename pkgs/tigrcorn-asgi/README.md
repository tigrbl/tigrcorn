<div align="center">
<h1>tigrcorn-asgi</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>ASGI3 scope, event, receive/send, and extension primitives for the Tigrcorn Python web server.</strong></p>

<a href="https://pypi.org/project/tigrcorn-asgi/"><img alt="PyPI version for tigrcorn-asgi" src="https://img.shields.io/pypi/v/tigrcorn-asgi?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-asgi/"><img alt="tigrcorn-asgi package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-asgi"><img alt="Downloads for tigrcorn-asgi" src="https://static.pepy.tech/badge/tigrcorn-asgi"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-asgi/README.md"><img alt="Hits for tigrcorn-asgi README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-asgi/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-asgi/"><img alt="asgi role package" src="https://img.shields.io/badge/role-asgi-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-asgi
```

```bash
pip install tigrcorn-asgi
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-asgi</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-asgi</code> owns ASGI scopes, ASGI events, receive/send channels, extensions, and connection state. Its import package is <code>tigrcorn_asgi</code>, and its declared package dependencies are: tigrcorn-core.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-asgi</code> when you want the asgi layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_asgi</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for ASGI scopes, ASGI events, receive/send channels, extensions, and connection state in the Tigrcorn package graph.

### Why is this package separate from runtime and protocols?

It isolates scopes, events, extensions, and receive/send contracts so protocol and runtime packages can share one ASGI3 boundary without duplicating event or scope logic.

## Features

- Owns ASGI scopes, ASGI events, receive/send channels, extensions, and connection state inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_asgi</code> import surface for module-oriented public surfaces.
- Declared runtime dependencies: tigrcorn-core.
- Optional dependency surface: none.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-asgi</code> when you need asgi-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
import tigrcorn_asgi

print(tigrcorn_asgi.__name__)
```

The package exposes its supported public surface through the <code>tigrcorn_asgi</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Keep new event and scope behavior aligned to ASGI3 contracts first, then layer protocol-specific behavior on top.
- Reuse the shared ASGI surface here before inventing protocol-local scope or event shapes.
- Validate extension and connection-state assumptions at this boundary before they leak into runtime code.

## License

Apache-2.0
