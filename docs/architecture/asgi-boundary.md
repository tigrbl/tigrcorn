# ASGI boundary

TigrCorn preserves the standard ASGI application boundary:

```python
async def app(scope, receive, send) -> None:
    ...
```

That is the compatibility contract shared with Uvicorn and Hypercorn.

The server may use any internal representation it wants, but it must present:

- standard `scope["type"]`
- standard HTTP / WebSocket / lifespan message types
- standard `receive()` and `send()` semantics
- standard header representation as `list[tuple[bytes, bytes]]`
