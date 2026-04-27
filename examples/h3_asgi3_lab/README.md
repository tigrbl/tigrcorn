# Tigrcorn H3 ASGI3 Lab

This example runs Tigrcorn as an ASGI3 server over HTTP/3 and WebTransport, plus
a small UI service for browser experiments.

The lab starts two containers:

- `tigrcorn-h3-asgi3`: Tigrcorn serving `examples.h3_asgi3_lab.app:app`
  over UDP with HTTP/3 and WebTransport enabled.
- `tigrcorn-h3-uix`: a lightweight static UI that opens a browser
  WebTransport session, sends bidirectional stream payloads, sends datagrams,
  and displays events returned by the ASGI3 app.

The runtime container generates a short-lived localhost certificate in a shared
Compose volume. The UI reads `/cert-hash.json` and passes the certificate hash
to the browser `WebTransport` constructor so local browser tests do not depend
on the OS trust store.

## Run

```powershell
docker compose -f examples/h3_asgi3_lab/docker-compose.yml up --build -d
```

Open:

- UI: `http://localhost:8091`
- WebTransport endpoint: `https://localhost:8445/wt`

## Stop

```powershell
docker compose -f examples/h3_asgi3_lab/docker-compose.yml down
```
