# Tigrcorn Static UIX Demo

This demo runs two containers:

- `tigrcorn-static-asgi3`: an ASGI3 app served by Tigrcorn on container port `8000`, published to `http://localhost:8020`.
- `tigrcorn-static-uix`: a lightweight browser client on container port `8080`, published to `http://localhost:8092`.

The ASGI3 app mounts `StaticFilesApp` at `/assets` and exposes `/api` plus `/api/list` for orientation.

```bash
docker compose -f examples/static_uix_demo/docker-compose.yml up --build -d
```

Open `http://localhost:8092` and run the prepared GET, HEAD, Range, and ETag experiments against `http://localhost:8020/assets/...`.

The UIX client shows Range and ETag as proof chains:

- `Range proof` sends `Range: bytes=<start>-<end>` and displays the resulting `206`, `Content-Range`, returned byte count, and response body preview.
- `ETag roundtrip` first fetches the selected asset and captures its `ETag`, then sends a second request with `If-None-Match` and displays the expected `304` response when the validator matches.
