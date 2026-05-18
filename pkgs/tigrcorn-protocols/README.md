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
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.11 supported" src="https://img.shields.io/badge/python-3.11-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.12 supported" src="https://img.shields.io/badge/python-3.12-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.13 supported" src="https://img.shields.io/badge/python-3.13-3776ab"></a>
<a href="src/tigrcorn_protocols/py.typed"><img alt="typed package" src="https://img.shields.io/badge/typed-py.typed-2f7ed8"></a>
<a href="https://pypi.org/project/tigrcorn-protocols/"><img alt="protocols role package" src="https://img.shields.io/badge/role-protocols-0a7f5a"></a>
</div>

## Install

~~~bash
pip install tigrcorn-protocols
~~~

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-protocols</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-protocols</code> owns HTTP/1.1, HTTP/2, HTTP/3, WebSocket, lifespan, rawframed, custom protocols, flow control, scheduler primitives, sessions, and streams. Its import package is <code>tigrcorn_protocols</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-config, tigrcorn-asgi, tigrcorn-http, tigrcorn-transports.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport runtime surfaces, typed package boundaries, and Apache 2.0 licensed infrastructure.

## Use It When

Use <code>tigrcorn-protocols</code> when you need protocol-level Tigrcorn handling for ASGI3 traffic, backpressure, flow control, HTTP/3, QUIC, WebSocket, or WebTransport behavior. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

~~~python
import tigrcorn_protocols

print(tigrcorn_protocols.__name__)
~~~

The package exposes its supported public surface through the <code>tigrcorn_protocols</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Package Graph

[tigrcorn](https://pypi.org/project/tigrcorn/) | [tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)