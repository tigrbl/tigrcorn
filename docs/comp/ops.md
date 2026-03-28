# Public operator surface matrix

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

| Operator surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| Package-owned HTTP/1 + HTTP/2 + HTTP/3 stack | C-OP | S | P | S | Granian publicly scopes HTTP/1 and HTTP/2; Hypercorn scopes HTTP/3 as optional/qualified. |
| Package-owned TLS 1.3 + X.509 + OCSP / CRL controls | C-OP | P | P | P | tigrcorn is the only server in this set with a package-owned, release-certified TLS/X.509/OCSP/CRL story. |
| Package-owned QUIC / RFC 9220 certification | C-OP | — | P | — | tigrcorn is the only one here with a published release certification bundle for HTTP/3 + RFC 9220. |
| Static offload as first-class server surface | C-OP | — | — | S | Granian and tigrcorn both expose server-native static delivery. |
| ASGI `http.response.pathsend` | C-OP | — | — | S | Granian and tigrcorn both document pathsend. |
| Lifecycle hook contract | C-OP | — | — | P | Granian documents embeddable server hooks; tigrcorn now documents a public lifecycle contract. |
| Embedded / programmatic server contract | C-OP | P | S | S | Uvicorn exposes `uvicorn.run`; Hypercorn documents `serve`; Granian documents embedded `Server`; tigrcorn documents `EmbeddedServer`. |
| Pipe / inproc / raw framed listeners | C-OP | — | — | — | tigrcorn-only transport/operator surface. |
| Proxy normalization as first-class CLI | C-OP | S | M | M | Hypercorn and Granian push proxy handling into wrappers/middleware. |
| Metrics exporter surface | C-OP | — | S | S | Hypercorn publishes StatsD; Granian publishes Prometheus metrics. |
| Machine-readable flag surface | C-OP | — | — | — | tigrcorn ships `cli_flag_surface.json` and related contracts. |
| Machine-readable promotion gate | C-OP | — | — | — | tigrcorn ships evaluators plus release-root manifests/indexes/summaries. |
| Current-state chain + release-root manifests | C-OP | — | — | — | tigrcorn has explicit current-state chain and frozen release roots. |
| Governed mutable / immutable repo markers | C-OP | — | — | — | Introduced in this checkpoint for tigrcorn. |
| Release governance and cert promotion playbook | C-OP | — | — | — | Introduced in this checkpoint for tigrcorn. |

Primary peer sources:

- Uvicorn settings: `https://www.uvicorn.org/settings/`
- Hypercorn docs: `https://hypercorn.readthedocs.io/en/latest/index.html`
- Granian README: `https://github.com/emmett-framework/granian`
