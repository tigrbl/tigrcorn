<div align="center">
<h1>tigrcorn-core</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Typed core primitives, errors, constants, and utilities shared by the Tigrcorn ASGI3 Python web server packages.</strong></p>

<a href="https://pypi.org/project/tigrcorn-core/"><img alt="PyPI version for tigrcorn-core" src="https://img.shields.io/pypi/v/tigrcorn-core?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-core/"><img alt="tigrcorn-core package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-core"><img alt="Downloads for tigrcorn-core" src="https://static.pepy.tech/badge/tigrcorn-core"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-core/README.md"><img alt="Hits for tigrcorn-core README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-core/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-core/"><img alt="core role package" src="https://img.shields.io/badge/role-core-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-core
```

```bash
pip install tigrcorn-core
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-core</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-core</code> owns constants, errors, types, and utils primitives. Its import package is <code>tigrcorn_core</code>, and its declared package dependencies are: none.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-core</code> when you want the core layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_core</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for constants, errors, types, and utils primitives in the Tigrcorn package graph.

### What does this package intentionally avoid?

It stays dependency-light and infrastructure-neutral so every higher Tigrcorn package can reuse shared constants, types, and core errors without pulling in HTTP, TLS, protocol, or runtime stacks.

## Features

- Owns constants, errors, types, and utils primitives inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_core</code> import surface for named public helpers and entrypoints.
- Declared runtime dependencies: none.
- Optional dependency surface: none.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-core</code> when you need core-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
import tigrcorn_core

print(tigrcorn_core.DEFAULT_HOST)
print(tigrcorn_core.DEFAULT_PORT)
```

The package exposes its supported public surface through the <code>tigrcorn_core</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn](https://pypi.org/project/tigrcorn/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn-http](https://pypi.org/project/tigrcorn-http/)
- [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Keep this package at the bottom of new dependency chains.
- Import protocol, runtime, or security behavior from higher packages instead of backfilling it here.
- Use the exported constants and error types instead of cloning parallel primitives in downstream packages.

## License

Apache-2.0
