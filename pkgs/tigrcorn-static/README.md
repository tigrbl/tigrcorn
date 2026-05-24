<div align="center">
<h1>tigrcorn-static</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Static file origin, file-send, validators, ranges, and cache-aware HTTP responses for the Tigrcorn ASGI server.</strong></p>

<a href="https://pypi.org/project/tigrcorn-static/"><img alt="PyPI version for tigrcorn-static" src="https://img.shields.io/pypi/v/tigrcorn-static?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-static/"><img alt="tigrcorn-static package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-static"><img alt="Downloads for tigrcorn-static" src="https://static.pepy.tech/badge/tigrcorn-static"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-static/README.md"><img alt="Hits for tigrcorn-static README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-static/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-static/"><img alt="static role package" src="https://img.shields.io/badge/role-static-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-static
```

```bash
pip install tigrcorn-static
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-static</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-static</code> owns static origin, pathsend, and file-send behavior. Its import package is <code>tigrcorn_static</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-asgi, tigrcorn-http.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-static</code> when you want the static layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_static</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for static origin, pathsend, and file-send behavior in the Tigrcorn package graph.

### Why keep static delivery separate?

Static origin, file-send, validators, cache-aware responses, and pathsend integration are separated so static delivery can evolve independently from protocol and runtime orchestration.

## Features

- Owns static origin, pathsend, and file-send behavior inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_static</code> import surface for named public helpers and entrypoints.
- Declared runtime dependencies: tigrcorn-core, tigrcorn-asgi, tigrcorn-http.
- Optional dependency surface: none.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-static</code> when you need static-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
import tigrcorn_static

print(tigrcorn_static.__name__)
```

The package exposes its supported public surface through the <code>tigrcorn_static</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/)
- [tigrcorn-http](https://pypi.org/project/tigrcorn-http/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Keep static file semantics and cache behavior rooted here so runtime and app embedding stay smaller.
- Use the shared validators and range handling instead of duplicating file-response logic elsewhere.
- Treat pathsend and file-send differences as documented public behavior, not as hidden implementation details.

## License

Apache-2.0
