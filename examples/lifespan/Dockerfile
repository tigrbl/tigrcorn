FROM python:3.13-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY pkgs ./pkgs

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
    && python -m pip install --no-cache-dir --no-deps -e .

COPY examples/lifespan ./examples/lifespan

EXPOSE 8000/tcp

CMD ["tigrcorn", "examples.lifespan.app:app", "--app-interface", "asgi3", "--host", "0.0.0.0", "--port", "8000", "--http", "1.1", "--protocol", "http1", "--lifespan", "on", "--log-level", "info"]
