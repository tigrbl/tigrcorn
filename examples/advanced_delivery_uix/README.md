# Tigrcorn Advanced Delivery UIX Demo

This demo runs a normal ASGI3 app under Tigrcorn and a separate lightweight UIX
client for probing delivery behavior.

```bash
docker compose -f examples/advanced_delivery_uix/docker-compose.yml up --build -d
```

Open `http://localhost:8022` for the UIX client. The Tigrcorn ASGI3 app is also
published directly at `http://localhost:8021`.

The UIX client exposes raw socket probes for:

- CONNECT relay through Tigrcorn to an echo endpoint in the UIX container.
- Response trailer fields.
- Content coding negotiation with `Accept-Encoding: gzip`.
- Conditional requests with both normal and `304 Not Modified` paths.
- Byte range requests with `206 Partial Content` and `416 Range Not Satisfiable`.
- `103 Early Hints` before the final response.
- Bounded `Alt-Svc` from the Tigrcorn `--alt-svc 'h3=":8443"; ma=60'` setting.

```bash
docker compose -f examples/advanced_delivery_uix/docker-compose.yml down
```
