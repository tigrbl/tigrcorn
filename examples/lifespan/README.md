# Tigrcorn ASGI3 Lifespan Example

This example shows a plain ASGI3 app using Tigrcorn's lifespan support.

Tigrcorn sends `lifespan.startup` before it starts accepting HTTP traffic when `--lifespan on` is set. The app marks itself ready during startup, exposes that state through `/healthz` and `/state`, then marks itself not ready when Tigrcorn sends `lifespan.shutdown`.

## Run Directly

```console
tigrcorn examples.lifespan.app:app --app-interface asgi3 --host 127.0.0.1 --port 8000 --http 1.1 --protocol http1 --lifespan on --log-level info
```

Then check the lifecycle-backed endpoints:

```console
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz').read().decode())"
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/state').read().decode())"
```

## Run In Docker

Build and start the example container:

```console
docker compose -f examples/lifespan/docker-compose.yml up --build
```

From another shell:

```console
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18081/state').read().decode())"
```

Stop the container with `Ctrl+C`. Tigrcorn will send `lifespan.shutdown`, and the container log will include `lifespan shutdown complete`.
