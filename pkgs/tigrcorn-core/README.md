<div align="center">
<h1>tigrcorn-core</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Typed core primitives, errors, constants, and utilities shared by the Tigrcorn ASGI3 Python web server packages.</strong></p>

[![SSOT governed](https://img.shields.io/badge/SSOT-governed-2f6f4e.svg)](https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json)

<a href="https://pypi.org/project/tigrcorn-core/"><img alt="PyPI version for tigrcorn-core" src="https://img.shields.io/pypi/v/tigrcorn-core?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-core/"><img alt="tigrcorn-core package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 supported" src="https://img.shields.io/badge/python-3.10-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.11 supported" src="https://img.shields.io/badge/python-3.11-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.12 supported" src="https://img.shields.io/badge/python-3.12-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.13 supported" src="https://img.shields.io/badge/python-3.13-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.14 supported" src="https://img.shields.io/badge/python-3.14-3776ab"></a>
<a href="src/tigrcorn_core/py.typed"><img alt="typed package" src="https://img.shields.io/badge/typed-py.typed-2f7ed8"></a>
<a href="https://pypi.org/project/tigrcorn-core/"><img alt="core role package" src="https://img.shields.io/badge/role-core-0a7f5a"></a>
</div>

## Install

~~~bash
pip install tigrcorn-core
~~~

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-core</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-core</code> owns constants, base errors, shared types, and dependency-light utility primitives. Its import package is <code>tigrcorn_core</code>, and its declared package dependencies are: none.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport runtime surfaces, typed package boundaries, and Apache 2.0 licensed infrastructure.

## Use It When

Use <code>tigrcorn-core</code> when you need stable Tigrcorn primitives without pulling runtime, protocol, transport, security, compatibility, or certification packages. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

~~~python
import tigrcorn_core

print(tigrcorn_core.__name__)
~~~

The package exposes its supported public surface through the <code>tigrcorn_core</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Package Graph

[tigrcorn](https://pypi.org/project/tigrcorn/) | [tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)
