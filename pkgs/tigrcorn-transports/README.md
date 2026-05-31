<div align="center">
<h1>tigrcorn-transports</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>TCP, UDP, Unix socket, pipe, in-process, listener, and QUIC transport primitives for the Tigrcorn server stack.</strong></p>

<a href="https://pypi.org/project/tigrcorn-transports/"><img alt="PyPI version for tigrcorn-transports" src="https://img.shields.io/pypi/v/tigrcorn-transports?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-transports/"><img alt="tigrcorn-transports package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-transports"><img alt="Downloads for tigrcorn-transports" src="https://static.pepy.tech/badge/tigrcorn-transports"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-transports/README.md"><img alt="Hits for tigrcorn-transports README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-transports/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-transports/"><img alt="transports role package" src="https://img.shields.io/badge/role-transports-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-transports
```

```bash
pip install tigrcorn-transports
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-transports</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-transports</code> owns listener registry, tcp, udp, unix, pipe, inproc, and quic transport primitives. Its import package is <code>tigrcorn_transports</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-config.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-transports</code> when you want the transports layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_transports</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for listener registry, tcp, udp, unix, pipe, inproc, and quic transport primitives in the Tigrcorn package graph.

### Which transport families live here?

TCP, UDP, Unix socket, pipe, in-process, listener-registry, and QUIC transport primitives all live in this package so higher protocol and runtime layers can remain transport-agnostic.

## Features

- Owns listener registry, tcp, udp, unix, pipe, inproc, and quic transport primitives inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_transports</code> import surface for module-oriented public surfaces.
- Declared runtime dependencies: tigrcorn-core, tigrcorn-config.
- Optional dependency surface: none.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-transports</code> when you need transports-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
import tigrcorn_transports

print(tigrcorn_transports.__name__)
```

The package exposes its supported public surface through the <code>tigrcorn_transports</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Keep transport primitives separate from protocol parsing and runtime orchestration.
- Treat QUIC and listener behavior as transport-level concerns here before exposing them upward.
- Use config-driven transport construction rather than hard-coding listener details in protocol packages.

## License

Apache-2.0
