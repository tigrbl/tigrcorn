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
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.11 supported" src="https://img.shields.io/badge/python-3.11-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.12 supported" src="https://img.shields.io/badge/python-3.12-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.13 supported" src="https://img.shields.io/badge/python-3.13-3776ab"></a>
<a href="src/tigrcorn_static/py.typed"><img alt="typed package" src="https://img.shields.io/badge/typed-py.typed-2f7ed8"></a>
<a href="https://pypi.org/project/tigrcorn-static/"><img alt="static role package" src="https://img.shields.io/badge/role-static-0a7f5a"></a>
</div>

## Install

~~~bash
pip install tigrcorn-static
~~~

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-static</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-static</code> owns static origin behavior, pathsend integration, file-send behavior, validators, ranges, and cache-aware static responses. Its import package is <code>tigrcorn_static</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-asgi, tigrcorn-http.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport runtime surfaces, typed package boundaries, and Apache 2.0 licensed infrastructure.

## Use It When

Use <code>tigrcorn-static</code> when you need Tigrcorn static file serving behavior without depending on the full runtime package. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

~~~python
import tigrcorn_static

print(tigrcorn_static.__name__)
~~~

The package exposes its supported public surface through the <code>tigrcorn_static</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Package Graph

[tigrcorn](https://pypi.org/project/tigrcorn/) | [tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)