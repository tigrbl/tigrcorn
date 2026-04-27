FROM python:3.13-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY pkgs ./pkgs
COPY examples/http11_asgi3_demo ./examples/http11_asgi3_demo

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

EXPOSE 8000/tcp 8080/tcp

CMD ["tigrcorn", "examples.http11_asgi3_demo.server:app", "--host", "0.0.0.0", "--port", "8000", "--protocol", "http1", "--http", "1.1", "--trailer-policy", "pass", "--timeout-keep-alive", "30", "--read-timeout", "10", "--write-timeout", "10", "--max-body-size", "1048576", "--max-header-size", "16384", "--server-header", "Tigrcorn-HTTP11-Demo", "--access-log"]
