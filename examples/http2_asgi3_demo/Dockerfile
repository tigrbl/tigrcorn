FROM python:3.13-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY pkgs ./pkgs
COPY examples/http2_asgi3_demo ./examples/http2_asgi3_demo

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

CMD ["tigrcorn", "examples.http2_asgi3_demo.app:app", "--app-interface", "asgi3", "--host", "0.0.0.0", "--port", "8000", "--http", "2", "--protocol", "http2", "--http2-max-concurrent-streams", "128", "--http2-adaptive-window", "--access-log"]
