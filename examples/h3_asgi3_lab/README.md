# Tigrcorn H3 ASGI3 Lab

This example runs Tigrcorn as an ASGI3 server over HTTP/3 on QUIC, plus a small
UI service for experiments.

The lab starts two containers:

- `tigrcorn-h3-asgi3`: Tigrcorn serving `examples.h3_asgi3_lab.app:app`
  over UDP with HTTP/3 enabled.
- `tigrcorn-h3-uix`: a lightweight UI that asks its local server to send HTTP/3
  requests to the Tigrcorn service over QUIC and displays the response.

The server and UI-side probe share a demo `--quic-secret`, matching Tigrcorn's
local HTTP/3 test path for direct QUIC packet protection.

The Compose stack bind-mounts `examples/` into the containers so edits to the
ASGI3 app and UI are picked up by container recreation without a full image
rebuild.

The UI probe targets the `tigrcorn-h3-asgi3` Compose service over the internal
Docker network.

## Run

```powershell
docker compose -f examples/h3_asgi3_lab/docker-compose.yml up --build -d
```

Open:

- UI: `http://localhost:8091`
- H3/QUIC endpoint: `https://localhost:8445/inspect`

## Stop

```powershell
docker compose -f examples/h3_asgi3_lab/docker-compose.yml down
```
