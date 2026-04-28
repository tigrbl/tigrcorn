FROM python:3.13-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY pkgs ./pkgs
COPY examples/wss_asgi3_lab ./examples/wss_asgi3_lab

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
      -e pkgs/tigrcorn-core \
      -e pkgs/tigrcorn-config \
      -e pkgs/tigrcorn-asgi \
      -e pkgs/tigrcorn-contract \
      -e pkgs/tigrcorn-transports \
      -e pkgs/tigrcorn-protocols \
      -e pkgs/tigrcorn-http \
      -e pkgs/tigrcorn-security \
      -e pkgs/tigrcorn-runtime \
      -e pkgs/tigrcorn-static \
      -e pkgs/tigrcorn-observability \
      -e pkgs/tigrcorn-compat \
      -e pkgs/tigrcorn-certification \
      -e .

EXPOSE 8443/tcp

CMD ["sh", "-c", "python -m examples.wss_asgi3_lab.cert_setup --out /certs --server-name localhost && python -m examples.wss_asgi3_lab.run_server & exec python -m examples.wss_asgi3_lab.tls_proxy --listen-host 0.0.0.0 --listen-port 8443 --upstream-host 127.0.0.1 --upstream-port 8000 --certfile /certs/server-cert.pem --keyfile /certs/server-key.pem"]
