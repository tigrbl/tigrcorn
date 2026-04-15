# ADR-1001: preserve the ASGI boundary

# ADR 1001 — preserve the ASGI boundary

Decision: TigrCorn remains an ASGI server at its public boundary.

Reason: that keeps it interchangeable with Uvicorn and Hypercorn and lets any standard
ASGI app run unchanged.
