# Lifecycle and EmbeddedServer contract

This document defines the public lifecycle-hook and embedding contract for the current `tigrcorn` package boundary.

It stays inside the current **[A][R]** application-hosting / runtime boundary and does not broaden the package into alternate app-interface or runtime-pluggability claims.

## Public lifecycle hooks

The package-owned lifecycle hook surface is configured on `ServerConfig.hooks`.

Supported hook lists:

- `on_startup`
- `on_shutdown`
- `on_reload`

Hooks may be synchronous callables or async callables.

### Hook signatures

`on_startup`

```python
Callable[[TigrCornServer], None | Awaitable[None]]
```

`on_shutdown`

```python
Callable[[TigrCornServer], None | Awaitable[None]]
```

`on_reload`

```python
Callable[[ServerConfig], None | Awaitable[None]]
```

Return values are ignored. Hooks are executed in registration order.

## Ordering relative to lifespan

The package-owned server ordering is:

### Startup ordering

1. `lifespan.startup()`
2. `on_startup` hooks
3. listener startup / bound-address synchronization
4. optional metrics / exporter startup

### Shutdown ordering

1. request-budget task cancellation
2. metrics listener shutdown
3. listener shutdown
4. scheduler shutdown
5. `lifespan.shutdown()`
6. `on_shutdown` hooks
7. optional exporter shutdown

### Reload ordering

For the polling reloader, the ordering is:

1. `on_reload` hooks
2. stop current child
3. spawn replacement child

## Failure semantics

### Startup hooks

Startup hook failures are **not suppressed**. An exception raised by an `on_startup` hook aborts startup and propagates to the caller.

### Shutdown hooks

Shutdown hook failures are **suppressed during `close()`**. They do not prevent listener shutdown, scheduler shutdown, or exporter shutdown.

### Reload hooks

Reload hook failures are **not suppressed** inside the reloader restart path. An exception raised by an `on_reload` hook aborts that restart attempt.

### Lifespan interaction

`lifespan.startup()` runs before `on_startup` hooks. `lifespan.shutdown()` runs before `on_shutdown` hooks.

## EmbeddedServer

`EmbeddedServer` is a first-class public embedding surface for programmatic startup and shutdown.

Public behaviors:

- `await start()` starts the underlying `TigrCornServer`
- repeated `await start()` calls are idempotent and reuse the same server instance
- `await close()` is a no-op before startup and shuts down the running server after startup
- `async with EmbeddedServer(...)` starts on enter and closes on exit
- `listeners` exposes the current listener objects
- `bound_endpoints()` returns currently bound socket/path endpoints

## Example: lifecycle hooks

```python
from tigrcorn.config.load import build_config
from tigrcorn.server.runner import TigrCornServer


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
            message = await receive()
        await send({"type": "lifespan.shutdown.complete"})
        return

    await receive()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok", "more_body": False})


async def on_startup(server):
    print("startup", server.config.listeners)


async def on_shutdown(server):
    print("shutdown", server.state.metrics.requests_served)


config = build_config(host="127.0.0.1", port=8000, lifespan="on")
config.hooks.on_startup = [on_startup]
config.hooks.on_shutdown = [on_shutdown]
server = TigrCornServer(app, config)
```

## Example: EmbeddedServer

```python
from tigrcorn import EmbeddedServer
from tigrcorn.config.load import build_config


async def app(scope, receive, send):
    await receive()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"embedded", "more_body": False})


config = build_config(host="127.0.0.1", port=0, lifespan="off")

async with EmbeddedServer(app, config) as embedded:
    print(embedded.bound_endpoints())
```

## Non-goals

This contract does **not** expand the package into:

- ASGI2 / WSGI / RSGI hosting
- Trio runtime support
- parser/backend / WebSocket-engine pluggability
- alternate embedding abstractions beyond the current `EmbeddedServer` / `TigrCornServer` package-owned surface
