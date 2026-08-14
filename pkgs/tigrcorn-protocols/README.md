<div align="center">
<h1>tigrcorn-protocols</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Protocol handlers for Tigrcorn HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, WebTransport, lifespan, and ASGI3 traffic.</strong></p>

<a href="https://pypi.org/project/tigrcorn-protocols/"><img alt="PyPI version for tigrcorn-protocols" src="https://img.shields.io/pypi/v/tigrcorn-protocols?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-protocols/"><img alt="tigrcorn-protocols package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-protocols"><img alt="Downloads for tigrcorn-protocols" src="https://static.pepy.tech/badge/tigrcorn-protocols"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-protocols/README.md"><img alt="Hits for tigrcorn-protocols README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-protocols/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-protocols/"><img alt="protocols role package" src="https://img.shields.io/badge/role-protocols-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-protocols
```

```bash
pip install tigrcorn-protocols
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-protocols</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-protocols</code> owns http1, http2, http3, websocket, lifespan, rawframed, custom protocols, flow control, scheduler primitives, sessions, and streams. Its import package is <code>tigrcorn_protocols</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-config, tigrcorn-asgi, tigrcorn-http, tigrcorn-transports.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-protocols</code> when you want the protocols layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_protocols</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for http1, http2, http3, websocket, lifespan, rawframed, custom protocols, flow control, scheduler primitives, sessions, and streams in the Tigrcorn package graph.

### What protocol families are implemented here?

This package is the main protocol plane for HTTP/1.1, HTTP/2, HTTP/3, WebSocket, WebTransport-adjacent protocol logic, lifespan, rawframed, scheduler primitives, sessions, and streams.

## Features

- Owns http1, http2, http3, websocket, lifespan, rawframed, custom protocols, flow control, scheduler primitives, sessions, and streams inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_protocols</code> import surface for module-oriented public surfaces.
- Declared runtime dependencies: tigrcorn-core, tigrcorn-config, tigrcorn-asgi, tigrcorn-http, tigrcorn-transports.
- Optional dependency surface: none.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-protocols</code> when you need protocols-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
import tigrcorn_protocols

print(tigrcorn_protocols.__name__)
```

The package exposes its supported public surface through the <code>tigrcorn_protocols</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/)
- [tigrcorn-http](https://pypi.org/project/tigrcorn-http/)
- [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-quic-cc](https://pypi.org/project/tigrcorn-quic-cc/) | [tigrcorn-quic-cc-reno](https://pypi.org/project/tigrcorn-quic-cc-reno/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Use this package for protocol-state machines and stream/session behavior, not for transport bootstrapping.
- Keep HTTP, WebSocket, and HTTP/3 behavior aligned with the certified protocol surface.
- Validate new protocol work against shared ASGI and HTTP helper layers before widening runtime claims.

## License

Apache-2.0
