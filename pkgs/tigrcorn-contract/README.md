<div align="center">
<h1>tigrcorn-contract</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>tigr-asgi-contract adapters and runtime-boundary classification for Tigrcorn ASGI3, WebSocket, and WebTransport surfaces.</strong></p>

<a href="https://pypi.org/project/tigrcorn-contract/"><img alt="PyPI version for tigrcorn-contract" src="https://img.shields.io/pypi/v/tigrcorn-contract?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-contract/"><img alt="tigrcorn-contract package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-contract"><img alt="Downloads for tigrcorn-contract" src="https://static.pepy.tech/badge/tigrcorn-contract"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-contract/README.md"><img alt="Hits for tigrcorn-contract README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-contract/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-contract/"><img alt="contract role package" src="https://img.shields.io/badge/role-contract-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-contract
```

```bash
pip install tigrcorn-contract
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-contract</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-contract</code> owns native contract app markers, contract scope validation, contract event validation, and boundary classification. Its import package is <code>tigrcorn_contract</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-asgi, tigr-asgi-contract.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-contract</code> when you want the contract layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_contract</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for native contract app markers, contract scope validation, contract event validation, and boundary classification in the Tigrcorn package graph.

### What does the contract layer validate?

It validates contract scopes, event ordering, endpoint metadata, runtime classification, and WebSocket or WebTransport boundary semantics against the tigr-asgi-contract surface.

## Features

- Owns native contract app markers, contract scope validation, contract event validation, and boundary classification inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_contract</code> import surface for named public helpers and entrypoints.
- Declared runtime dependencies: tigrcorn-core, tigrcorn-asgi, tigr-asgi-contract.
- Optional dependency surface: none.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-contract</code> when you need contract-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
from tigrcorn_contract import contract_scope, validate_scope

scope = contract_scope("http", path="/")
print(validate_scope(scope))
```

Namespace discovery starts with `import tigrcorn_contract`.

The package exposes its supported public surface through the <code>tigrcorn_contract</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-quic-cc](https://pypi.org/project/tigrcorn-quic-cc/) | [tigrcorn-quic-cc-reno](https://pypi.org/project/tigrcorn-quic-cc-reno/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Use this package when you need contract validation or classification rather than embedding that logic in protocol handlers.
- Keep new WebSocket, WebTransport, and endpoint-metadata semantics grounded in the contract surface here.
- Update runtime-boundary classification together with any new contract-facing feature rows.

## License

Apache-2.0
