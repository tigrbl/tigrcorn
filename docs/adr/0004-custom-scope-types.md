# ADR 0004 — custom scope types are allowed behind the ASGI surface

Decision: custom transports may expose custom scope types in the future.

Reason: the server needs an escape hatch for non-HTTP, non-WebSocket protocols while still
preserving strict compatibility for the standard protocol set.
