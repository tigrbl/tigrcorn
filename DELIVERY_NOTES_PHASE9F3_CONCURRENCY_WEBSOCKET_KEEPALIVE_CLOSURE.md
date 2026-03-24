# Delivery notes — Phase 9F3 concurrency and WebSocket keepalive closure

This checkpoint closes the remaining public flag/runtime gaps from Phase 9F:

- `--limit-concurrency`
- `--websocket-ping-interval`
- `--websocket-ping-timeout`

Result:

- authoritative boundary: green
- strict target boundary: not green
- flag surface: green
- operator surface: green
- performance target: not green
- promotion target: not green

The remaining blockers are the preserved-but-non-passing HTTP/3 `aioquic` scenarios plus the strict performance / gate-hardening phases.
