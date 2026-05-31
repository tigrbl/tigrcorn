# Tigrcorn WebSocket UIX demo

This example runs a Tigrcorn-hosted ASGI3 WebSocket app and a separate
lightweight browser client.

## Run

```console
docker compose -f examples/websocket_uix_demo/docker-compose.yml up --build -d
```

Open `http://localhost:18091`.

The ASGI3 backend listens on `http://localhost:8765` and exposes:

- `GET /health`
- `GET /state`
- `WS /ws`

Stop it with:

```console
docker compose -f examples/websocket_uix_demo/docker-compose.yml down
```
