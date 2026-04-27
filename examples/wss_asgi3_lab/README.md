# Tigrcorn WSS ASGI3 Lab

This example runs a plain ASGI3 application behind Tigrcorn with a TLS WebSocket endpoint and a small browser UIX client.

Run it with Docker Compose:

```sh
docker compose -f examples/wss_asgi3_lab/docker-compose.yml up --build
```

Open the client at:

```text
http://localhost:8093
```

The Tigrcorn ASGI3 app listens at:

```text
wss://localhost:8443/ws
https://localhost:8443/health
```

Because the demo generates a local self-signed localhost certificate, open `https://localhost:8443/health` once and accept the browser warning before connecting from the UI. After that, the UI can open `wss://localhost:8443/ws`.

The server is intentionally ordinary ASGI3:

- `websocket.connect` is accepted with `websocket.accept`
- text frames are echoed as JSON
- binary frames are counted and reported
- `/close` sends `websocket.close`
- Tigrcorn runtime flags enable TLS, WebSocket, permessage-deflate, message limits, and ping settings
