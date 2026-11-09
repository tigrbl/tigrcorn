# Tigrcorn HTTP/2 ASGI3 Demo

This example runs a Tigrcorn ASGI3 app with HTTP/2 enabled and a lightweight UIX client for interactive experiments.

```bash
docker compose -f examples/http2_asgi3_demo/docker-compose.yml up --build
```

Open `http://localhost:8089` for the UIX client. The client container serves the browser UI and proxies experiment requests to `tigrcorn-h2-app:8000` using HTTP/2 prior knowledge.

The Tigrcorn app container is also published on `localhost:8002` for direct HTTP/2 clients.

Key Tigrcorn flags in the app container:

```bash
tigrcorn examples.http2_asgi3_demo.app:app \
  --config examples/http2_asgi3_demo/tigrcorn-h2.toml \
  --app-interface asgi3 \
  --host 0.0.0.0 \
  --port 8000 \
  --http 2 \
  --protocol http2 \
  --http2-max-concurrent-streams 128 \
  --http2-initial-connection-window-size 131072 \
  --http2-initial-stream-window-size 98304 \
  --http2-adaptive-window \
  --access-log
```

The config file enables `http.enable_h2c = true`, which allows direct HTTP/2 prior-knowledge requests in this local cleartext Docker lab.

Use the UI to run:

- `GET /` and inspect the ASGI `scope["http_version"]`.
- `GET /stream?chunks=5&delay=0.05` and inspect streamed response chunks.
- `POST /echo` and confirm body delivery through ASGI `receive`.
- Multiplexed request batches from the UIX proxy into the Tigrcorn HTTP/2 listener.
