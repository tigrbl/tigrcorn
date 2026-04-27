FROM python:3.13-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY pkgs ./pkgs
COPY tests/fixtures_certs ./tests/fixtures_certs
COPY examples/webtransport_mtls_demo ./examples/webtransport_mtls_demo

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
      -e ".[certification]"

EXPOSE 8443/udp 8080/tcp

CMD ["tigrcorn", "examples.webtransport_mtls_demo.server:app", "--transport", "udp", "--host", "0.0.0.0", "--port", "8443", "--protocol", "webtransport", "--http", "3", "--ssl-certfile", "tests/fixtures_certs/interop-localhost-cert.pem", "--ssl-keyfile", "tests/fixtures_certs/interop-localhost-key.pem", "--ssl-ca-certs", "tests/fixtures_certs/interop-client-cert.pem", "--ssl-require-client-cert", "--webtransport-max-sessions", "8", "--webtransport-max-streams", "64", "--webtransport-max-datagram-size", "1200", "--webtransport-origin", "https://localhost:8088,http://localhost:8088", "--webtransport-path", "/wt"]
