> Path note: `examples/advanced_delivery/` is the canonical current integrated Phase 4 example tree. `examples/advanced_protocol_delivery/` is retained as an archival compatibility path for focused single-feature examples from the original Phase 4 checkpoint.

# Advanced protocol and delivery example matrix

This directory packages the Phase 4 checkpoint examples and maps them onto the existing repository example and fixture set.

## New Phase 4 examples

- `early_hints_app.py` + `early_hints_client_http1.py`
- `alt_svc_app.py` + `alt_svc_client_http1.py`
- `runtime_embedding.py`

## Existing example and fixture pairings used by this checkpoint

| Lane | Server app | Matching client / fixture |
| --- | --- | --- |
| HTTP/1.1 basic | `examples/echo_http/app.py` | `curl` / raw socket examples |
| HTTP/2 basic | `examples/echo_http/app.py` | `tests/fixtures_pkg/external_h2_http_client.py` |
| HTTP/3 basic | `examples/echo_http/app.py` | `tests/fixtures_pkg/external_http3_client.py` |
| WebSocket | `examples/websocket_echo/app.py` | `tests/fixtures_pkg/external_websocket_client.py` |
| permessage-deflate | `examples/websocket_echo/app.py` | `tests/fixtures_pkg/external_websocket_client.py` |
| CONNECT relay | `tests/fixtures_pkg/_connect_relay_fixture.py` | `tests/fixtures_pkg/interop_http_client.py` |
| trailer fields | `tests/fixtures_pkg/interop_trailer_app.py` | repository trailer tests and external HTTP clients |
| content coding | `tests/fixtures_pkg/interop_content_coding_app.py` | `tests/fixtures_pkg/external_curl_client.py` |
| static + range + ETag | `examples/http_entity_static/app.py` | `examples/http_entity_static/client_http1.py` |
| Early Hints | `examples/advanced_protocol_delivery/early_hints_app.py` | `examples/advanced_protocol_delivery/early_hints_client_http1.py` |
| Alt-Svc | `examples/advanced_protocol_delivery/alt_svc_app.py` | `examples/advanced_protocol_delivery/alt_svc_client_http1.py` |

## Notes

- HTTP/2 and HTTP/3 are shown as deployment modes for the same ASGI app surface rather than separate app implementations.
- The checkpoint keeps protocol-aware clients close to the existing interop fixture set instead of cloning them into multiple redundant example trees.
- The runtime embedding example focuses on startup/shutdown hooks and config-driven embedding, not on replacing the full process supervisor surface.
