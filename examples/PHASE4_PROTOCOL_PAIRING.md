> Current pairing note: this is the canonical current Phase 4 pairing matrix. `examples/advanced_delivery/` is the canonical integrated example tree; `examples/advanced_protocol_delivery/` is retained as an archival compatibility path.

# Phase 4 Protocol Pairing Matrix

This checkpoint keeps Phase 4 inside the direct app-server/runtime boundary. Some lanes use top-level examples and some reuse fixture apps or clients that are already part of the repository's conformance inventory.

| Lane | Server app | Matching client / driver | Notes |
| --- | --- | --- | --- |
| HTTP/1.1 basic + Early Hints | `examples/advanced_delivery/app.py` | `examples/advanced_delivery/client_http1.py` | Demonstrates 103 and final response over HTTP/1.1 |
| HTTP/2 basic + Early Hints | `examples/advanced_delivery/app.py` | `examples/advanced_delivery/client_http2.py` | Demonstrates 103 and final response over HTTP/2 |
| HTTP/3 basic | `examples/advanced_delivery/app.py` | `examples/advanced_delivery/client_http3.py` | Demonstrates request/response over HTTP/3 |
| Static + Range + ETag | `examples/http_entity_static/app.py` | `examples/http_entity_static/client_http1.py` | Reuses the Phase 2 entity semantics pair |
| WebSocket | `examples/websocket_echo/app.py` | `tests/fixtures_pkg/external_websocket_client.py` | Same-stack fixture client |
| permessage-deflate | `examples/websocket_echo/app.py` | `tests/fixtures_pkg/external_h2_websocket_client.py`, `tests/fixtures_pkg/external_h3_websocket_client.py` | Reuses H2/H3 WebSocket conformance clients |
| CONNECT relay | package runtime / relay fixture | `tests/fixtures_pkg/_connect_relay_fixture.py` | Fixture covers CONNECT tunnel scenarios |
| trailers | `tests/fixtures_pkg/interop_trailer_app.py` | `tests/fixtures_pkg/external_h2_http_client.py --response-trailers` or `tests/fixtures_pkg/external_curl_client.py --response-trailers` | Conformance-oriented example lane |
| content coding | `tests/fixtures_pkg/interop_content_coding_app.py` | `tests/fixtures_pkg/external_h2_http_client.py --content-coding` or `tests/fixtures_pkg/external_curl_client.py --content-coding` | Conformance-oriented example lane |
| Alt-Svc | `examples/advanced_delivery/app.py` with server flags `--alt-svc-auto` or `--alt-svc` and UDP HTTP/3 listener | `examples/advanced_delivery/client_http1.py` or `client_http2.py` | Advertisement is normally emitted on non-H3 responses |

## Suggested launch commands

### HTTP/1.1 / HTTP/2 advanced delivery

```bash
PYTHONPATH=src python -m tigrcorn examples.advanced_delivery.app:app --bind 127.0.0.1:8000 --http 1.1 --http 2
```

### HTTP/1.1 / HTTP/2 + Alt-Svc advertisement for HTTP/3 bootstrap

```bash
PYTHONPATH=src python -m tigrcorn examples.advanced_delivery.app:app \
  --bind 127.0.0.1:8000 \
  --quic-bind 127.0.0.1:8443 \
  --http 1.1 --http 2 --http 3 \
  --alt-svc-auto --alt-svc-ma 3600
```

### HTTP/3 direct server

```bash
PYTHONPATH=src python -m tigrcorn examples.advanced_delivery.app:app \
  --quic-bind 127.0.0.1:8443 \
  --http 3 \
  --transport udp \
  --protocol http3
```

The Phase 4 checkpoint is still honest about current limits:

- runtime `trio` is **not** part of the supported public runtime surface in this checkpoint; the `runtime-trio` extra only reserves a future/internal dependency path and does not enable `--runtime trio`
- selecting `--runtime uvloop` requires the declared `runtime-uvloop` extra
- Brotli content-coding / `.br` static sidecars require the declared `compression` extra
- HTTP/2 / HTTP/3 prioritization remains transport-adjacent and is not expanded into a new product surface in this checkpoint
- example coverage is release-oriented, but some lanes intentionally reuse conformance fixture apps or clients already present in the repository
