# Tigrcorn package boundaries

Tigrcorn is moving from one implementation-heavy distribution toward a monorepo workspace with several publishable packages. The `tigrcorn` package remains the stable umbrella install and public API facade while implementation migrates into packages with one-way dependencies.

## Boundary rule

Dependency direction is strict:

`core -> config/http/asgi -> contract/transports/security -> protocols/static/observability -> runtime -> compat -> certification -> tigrcorn umbrella`

Lower layers must not import higher layers. Leaf packages such as `tigrcorn-compat` and `tigrcorn-certification` must never become dependencies of runtime, protocol, transport, security, ASGI, config, or core packages.

## Packages

| Distribution | Import name | Owns |
| --- | --- | --- |
| `tigrcorn-core` | `tigrcorn_core` | constants, base exceptions, type aliases, dependency-light shared primitives |
| `tigrcorn-config` | `tigrcorn_config` | config models, normalization, validation, profiles, file/env loading |
| `tigrcorn-asgi` | `tigrcorn_asgi` | ASGI scopes, events, receive/send channels, extensions, connection state |
| `tigrcorn-contract` | `tigrcorn_contract` | `tigr-asgi-contract` adapters, native app markers, contract validation, boundary classification |
| `tigrcorn-transports` | `tigrcorn_transports` | listener registry and TCP, UDP, Unix, pipe, inproc, QUIC transport primitives |
| `tigrcorn-http` | `tigrcorn_http` | structured fields, range, etag, conditionals, Alt-Svc, Early Hints, HTTP helper surfaces |
| `tigrcorn-protocols` | `tigrcorn_protocols` | HTTP/1, HTTP/2, HTTP/3, WebSocket, lifespan, rawframed, custom protocol handlers |
| `tigrcorn-security` | `tigrcorn_security` | TLS, TLS 1.3, X.509, ALPN, cipher policy, certificate helpers |
| `tigrcorn-runtime` | `tigrcorn_runtime` | server runner, app loading, bootstrap, workers, signals, shutdown, embedding |
| `tigrcorn-static` | `tigrcorn_static` | package-owned static origin and file-send behavior |
| `tigrcorn-observability` | `tigrcorn_observability` | logging, metrics, tracing, evidence metadata export |
| `tigrcorn-compat` | `tigrcorn_compat` | uvicorn/hypercorn interop, ASGI3 probes, conformance helpers |
| `tigrcorn-certification` | `tigrcorn_certification` | release gates, certification environment, external peer matrices, strict promotion checks |

## Migration status

The first extracted implementation package is `tigrcorn-core`. The legacy modules `tigrcorn.constants`, `tigrcorn.errors`, and `tigrcorn.types` are compatibility shims that re-export from `tigrcorn_core`.

All other package directories are scaffolded with metadata, import names, and typed package markers. Implementation should move package by package only after import-boundary tests pass for the previous layer.

## Public compatibility

The top-level `tigrcorn` package remains the public install target. These imports stay stable during the split:

- `tigrcorn.run`
- `tigrcorn.serve`
- `tigrcorn.serve_import_string`
- `tigrcorn.StaticFilesApp`
- `tigrcorn.EmbeddedServer`
- `tigrcorn.NativeContractApp`
- `tigrcorn.native_contract_app`
- `tigrcorn.mark_native_contract_app`

Internal imports should migrate toward package-owned import names only after the owning package contains the implementation.
