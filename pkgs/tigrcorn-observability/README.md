<div align="center">
<h1>tigrcorn-observability</h1>
<img
  src="https://raw.githubusercontent.com/Tigrbl/tigrcorn/master/assets/tigrcorn_logo.png"
  alt="Tigrcorn tiger-unicorn logo"
  width="140"
/>

<p><strong>Logging, metrics, tracing, DoS warning events, and release-evidence metadata for the Tigrcorn Python web server.</strong></p>

[![SSOT governed](https://img.shields.io/badge/SSOT-governed-2f6f4e.svg)](https://github.com/Tigrbl/tigrcorn/blob/master/.ssot/registry.json)

<a href="https://pypi.org/project/tigrcorn-observability/"><img alt="PyPI version for tigrcorn-observability" src="https://img.shields.io/pypi/v/tigrcorn-observability?label=PyPI"></a>
<a href="https://pypi.org/project/tigrcorn-observability/"><img alt="tigrcorn-observability package on PyPI" src="https://img.shields.io/badge/package-PyPI-blue"></a>
<a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-525252"></a>
<a href="pyproject.toml"><img alt="Python 3.10 supported" src="https://img.shields.io/badge/python-3.10-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.11 supported" src="https://img.shields.io/badge/python-3.11-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.12 supported" src="https://img.shields.io/badge/python-3.12-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.13 supported" src="https://img.shields.io/badge/python-3.13-3776ab"></a>
<a href="pyproject.toml"><img alt="Python 3.14 supported" src="https://img.shields.io/badge/python-3.14-3776ab"></a>
<a href="src/tigrcorn_observability/py.typed"><img alt="typed package" src="https://img.shields.io/badge/typed-py.typed-2f7ed8"></a>
<a href="https://pypi.org/project/tigrcorn-observability/"><img alt="observability role package" src="https://img.shields.io/badge/role-observability-0a7f5a"></a>
</div>

<p align="center"><a href="https://discord.gg/jzvrbEtTtt"><img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20chat-5865F2?logo=discord&amp;logoColor=white"></a></p>


## Install

~~~bash
pip install tigrcorn-observability
~~~

Use the aggregate [tigrcorn](https://pypi.org/project/tigrcorn/) distribution when you want the full ASGI3 Python web server stack. Install <code>tigrcorn-observability</code> directly when you want only this package boundary and its declared dependencies.

## What It Owns

<code>tigrcorn-observability</code> owns logging, metrics, tracing, DoS warning events, and evidence metadata export surfaces. Its import package is <code>tigrcorn_observability</code>, and its declared package dependencies are: tigrcorn-core, tigrcorn-config.

This package page is written for developers searching for Tigrcorn ASGI3 server components, Python web server packages, HTTP/3 and QUIC support, WebSocket and WebTransport runtime surfaces, typed package boundaries, and Apache 2.0 licensed infrastructure.

## Use It When

Use <code>tigrcorn-observability</code> when you need searchable Tigrcorn observability signals for runtime telemetry, protocol stalls, metrics, tracing, or release evidence. It is part of Tigrcorn's split-package architecture, so it can be installed independently while remaining linked to the rest of the Tigrcorn package family on PyPI.

## Import Surface

~~~python
import tigrcorn_observability

print(tigrcorn_observability.__name__)
~~~

The package exposes its supported public surface through the <code>tigrcorn_observability</code> namespace. The root [tigrcorn](https://pypi.org/project/tigrcorn/) package keeps compatibility shims for users who install the full server distribution.

## Package Graph

[tigrcorn](https://pypi.org/project/tigrcorn/) | [tigrcorn-core](https://pypi.org/project/tigrcorn-core/) | [tigrcorn-config](https://pypi.org/project/tigrcorn-config/) | [tigrcorn-asgi](https://pypi.org/project/tigrcorn-asgi/) | [tigrcorn-contract](https://pypi.org/project/tigrcorn-contract/) | [tigrcorn-transports](https://pypi.org/project/tigrcorn-transports/) | [tigrcorn-protocols](https://pypi.org/project/tigrcorn-protocols/) | [tigrcorn-http](https://pypi.org/project/tigrcorn-http/) | [tigrcorn-security](https://pypi.org/project/tigrcorn-security/) | [tigrcorn-runtime](https://pypi.org/project/tigrcorn-runtime/) | [tigrcorn-static](https://pypi.org/project/tigrcorn-static/) | [tigrcorn-observability](https://pypi.org/project/tigrcorn-observability/) | [tigrcorn-compat](https://pypi.org/project/tigrcorn-compat/) | [tigrcorn-certification](https://pypi.org/project/tigrcorn-certification/)
