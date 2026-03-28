# RFC target matrix

Reviewed on: `2026-03-28`

Legend:

- `C-RFC` — tigrcorn implements the surface and includes it in the current certified RFC boundary.
- `C-OP` — tigrcorn implements the surface and includes it in the current certified public/operator surface.
- `S` — current official docs show first-class public support.
- `Cfg` — current official docs show public support through a primary config surface rather than a dedicated CLI switch.
- `P` — partial, optional, qualified, or draft support.
- `M` — middleware/wrapper based support instead of a first-class server surface.
- `O` — intentionally outside tigrcorn's current product boundary.
- `—` — no current official public support claim found in the reviewed primary docs.

| RFC target | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| RFC 9112 HTTP/1.1 | C-RFC | S | S | S | Core HTTP/1.1 server path. |
| RFC 9113 HTTP/2 | C-RFC | — | S | S | Hypercorn and Granian publicly document HTTP/2. |
| RFC 9114 HTTP/3 | C-RFC | — | P | — | Hypercorn documents a QUIC/HTTP/3 path via `--quic-bind`; Granian says HTTP/3 is future work. |
| RFC 9000 QUIC transport | C-RFC | — | P | — | Hypercorn's public QUIC surface is optional/qualified. |
| RFC 9001 QUIC-TLS | C-RFC | — | P | — | Hypercorn's public QUIC/TLS path is qualified by its optional HTTP/3 stack. |
| RFC 9002 QUIC recovery | C-RFC | — | P | — | Hypercorn's public docs do not independently certify recovery behavior. |
| RFC 7541 HPACK | C-RFC | — | P | P | Peer docs imply HPACK through HTTP/2 support but do not certify it separately. |
| RFC 9204 QPACK | C-RFC | — | P | — | Peer docs do not expose a package-owned QPACK claim comparable to tigrcorn. |
| RFC 6455 WebSocket | C-RFC | S | S | S | All three peers publicly document WebSocket support. |
| RFC 7692 permessage-deflate | C-RFC | S | — | — | Uvicorn exposes per-message-deflate; Hypercorn and Granian do not document it in the reviewed sources. |
| RFC 8441 WebSocket over HTTP/2 | C-RFC | — | S | — | Hypercorn publicly documents WebSockets over HTTP/2. |
| RFC 9220 WebSocket over HTTP/3 | C-RFC | — | — | — | Only tigrcorn currently ships and certifies this surface in the reviewed set. |
| RFC 8446 TLS 1.3 | C-RFC | P | P | P | Peer docs expose TLS controls but do not publish a comparable package-owned TLS 1.3 certification claim. |
| RFC 7301 ALPN | C-RFC | — | S | — | Hypercorn documents ALPN protocol control. |
| RFC 5280 X.509 validation | C-RFC | P | P | P | Peer docs expose CA/client-certificate settings but not tigrcorn-style package-owned certification. |
| RFC 6960 OCSP | C-RFC | — | — | — | No peer public OCSP surface was found in the reviewed docs. |
| RFC 9110 §9.3.6 CONNECT relay | C-RFC | — | — | — | tigrcorn-only surface in this comparison. |
| RFC 9110 §6.5 trailer fields | C-RFC | — | — | — | tigrcorn-only public surface in this comparison. |
| RFC 9110 §8 content coding | C-RFC | — | — | — | tigrcorn-only public content-coding policy surface in this comparison. |
| RFC 7232 conditional requests | C-RFC | — | — | — | tigrcorn-only boundary target in this comparison. |
| RFC 7233 range requests | C-RFC | — | — | — | tigrcorn-only boundary target in this comparison. |
| RFC 8297 Early Hints | C-RFC | — | — | — | tigrcorn-only boundary target in this comparison. |
| RFC 7838 §3 Alt-Svc header | C-RFC | — | Cfg | — | Hypercorn documents `alt_svc_headers` via config; tigrcorn ships CLI + certified bounded header surface. |

Primary peer sources:

- Uvicorn: `https://www.uvicorn.org/settings/`
- Uvicorn WebSockets: `https://www.uvicorn.org/concepts/websockets/`
- Hypercorn docs: `https://hypercorn.readthedocs.io/en/latest/how_to_guides/configuring.html`
- Hypercorn HTTP/2: `https://hypercorn.readthedocs.io/en/stable/discussion/http2.html`
- Granian README: `https://github.com/emmett-framework/granian`
