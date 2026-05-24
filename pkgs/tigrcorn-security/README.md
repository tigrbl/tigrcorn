<div align="center">
<h1>tigrcorn-security</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>TLS 1.3, mTLS, X.509, ALPN, OCSP, CRL, and certificate policy surfaces for the Tigrcorn Python web server.</strong></p>

<a href="https://pypi.org/project/tigrcorn-security/"><img alt="PyPI version for tigrcorn-security" src="https://img.shields.io/pypi/v/tigrcorn-security?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-security/"><img alt="tigrcorn-security package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="https://pepy.tech/project/tigrcorn-security"><img alt="Downloads for tigrcorn-security" src="https://static.pepy.tech/badge/tigrcorn-security"></a>
<a href="https://github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-security/README.md"><img alt="Hits for tigrcorn-security README" src="https://hits.sh/github.com/tigrbl/tigrcorn/blob/master/pkgs/tigrcorn-security/README.md.svg?label=hits"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 | 3.11 | 3.12 | 3.13 | 3.14 supported" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-3776ab"></a>
<a href="https://pypi.org/project/tigrcorn-security/"><img alt="security role package" src="https://img.shields.io/badge/role-security-0a7f5a"></a>
</div>

<p align="center"><a href="https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json"><img alt="SSOT governed" src="https://img.shields.io/badge/SSOT-governed-2f6f4e.svg"></a> <a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>

## Install

```bash
uv add tigrcorn-security
```

```bash
pip install tigrcorn-security
```

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-security</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-security</code> owns tls, tls13, x509, alpn, cipher policy, and certificate helpers. Its import package is <code>tigrcorn_security</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-config.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport-adjacent surfaces, and Apache 2.0 licensed infrastructure.

## Why Use This?

Use <code>tigrcorn-security</code> when you want the security layer as a direct install target instead of the full server bundle. It lets application, operator, or certification workflows depend on this boundary explicitly while keeping the broader Tigrcorn runtime assembled from smaller repo-owned package surfaces.

## FAQ

### What does this package export?

The package exports through the <code>tigrcorn_security</code> namespace and keeps the root <code>tigrcorn</code> package as the compatibility umbrella.

### Which boundary does this package own?

It is the package boundary for tls, tls13, x509, alpn, cipher policy, and certificate helpers in the Tigrcorn package graph.

### Which security surfaces live here?

TLS 1.3, mTLS, X.509, ALPN, certificate helpers, cipher policy, and related validation surfaces are concentrated here so runtime and protocol layers can consume a consistent security boundary.

## Features

- Owns tls, tls13, x509, alpn, cipher policy, and certificate helpers inside the Tigrcorn split-package architecture.
- Publishes the <code>tigrcorn_security</code> import surface for module-oriented public surfaces.
- Declared runtime dependencies: tigrcorn-core, tigrcorn-config.
- Optional dependency surface: cryptography.
- Supports Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Use It When

Use <code>tigrcorn-security</code> when you need security-level behavior without pulling the entire server stack into the import surface. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

```python
import tigrcorn_security

print(tigrcorn_security.__name__)
```

The package exposes its supported public surface through the <code>tigrcorn_security</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Related Packages

- [tigrcorn-core](https://pypi.org/project/tigrcorn-core/)
- [tigrcorn-config](https://pypi.org/project/tigrcorn-config/)
- [tigrcorn](https://pypi.org/project/tigrcorn/)

## Package Graph

[tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)

## Best Practices

- Keep TLS, certificate, and ALPN logic centralized here instead of scattering policy code across runtime modules.
- Pull cryptography-backed extras only for deployments that need X.509 or certificate helper behavior.
- Document operator-visible security behavior against this package boundary before claiming support at the repo root.

## License

Apache-2.0
