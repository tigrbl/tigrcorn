# HTTP/1.1 ASGI3 Demo

This example runs a plain ASGI3 application under Tigrcorn's HTTP/1.1 protocol
path and a separate lightweight Python static-client container for experiments.

Run it:

```sh
docker compose -f examples/http11_asgi3_demo/docker-compose.yml up --build -d
```

Open:

- ASGI3 app: `http://localhost:8011`
- UIX client: `http://localhost:8012`

The Tigrcorn container starts with the HTTP/1.1-specific operator surface:

```sh
tigrcorn examples.http11_asgi3_demo.server:app \
  --host 0.0.0.0 \
  --port 8000 \
  --protocol http1 \
  --http 1.1 \
  --trailer-policy pass \
  --timeout-keep-alive 30 \
  --read-timeout 10 \
  --write-timeout 10 \
  --max-body-size 1048576 \
  --max-header-size 16384 \
  --server-header Tigrcorn-HTTP11-Demo \
  --access-log
```

The ASGI3 app exposes:

- `/inspect` for ASGI scope and request header inspection.
- `/echo` for POST body handling.
- `/stream` for chunked response-body delivery.
- `/trailers` for ASGI `http.response.trailers`.
- `/early-hints` for an interim `103` response before the final `200`.

Stop it:

```sh
docker compose -f examples/http11_asgi3_demo/docker-compose.yml down
```
