# CLI feature matrix

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

| CLI feature family | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| App factory loading | C-OP | S | — | S | Granian and Uvicorn expose `--factory`; Hypercorn expects an app object path. |
| Working-dir / app-dir control | C-OP | S | Cfg | S | Hypercorn exposes `application_path` via config. |
| Config file loading | C-OP | — | S | — | Hypercorn supports TOML/Python/module config. |
| Env-file loading | C-OP | S | — | S | Granian requires its dotenv extra for env files. |
| Env-prefix override | C-OP | — | — | — | tigrcorn-only public env-prefix surface. |
| Reload + watch filters | C-OP | S | P | S | Hypercorn documents reload; Granian documents reload paths/ignore controls. |
| Workers + recycling | C-OP | S | S | S | All four expose worker/process controls; exact semantics differ. |
| Runtime / worker-class selection | C-OP | P | S | S | Uvicorn exposes loop/http/ws selectors; Hypercorn exposes worker class; Granian exposes loop/runtime mode/task implementation. |
| Host / port bind | C-OP | S | S | S | Common across all four. |
| Unix domain socket bind | C-OP | S | S | S | Common across all four. |
| FD bind | C-OP | S | S | — | Granian docs do not expose an FD bind in the reviewed README. |
| Multi-bind / endpoint grammar | C-OP | — | S | P | Hypercorn documents multiple binds; Granian exposes route/mount pairs but not Hypercorn-style bind grammar. |
| QUIC / HTTP/3 bind | C-OP | — | S | — | Hypercorn exposes `--quic-bind`; Uvicorn and Granian do not in the reviewed docs. |
| Transport selection incl. pipe/inproc/raw | C-OP | — | — | — | tigrcorn-only surface. |
| Socket ownership / permissions | C-OP | — | S | S | Hypercorn exposes user/group/umask; Granian exposes UDS permissions and process controls. |
| Server-native static route / mount | C-OP | — | — | S | Granian and tigrcorn expose first-class static serving. |
| Static dir-to-file / index control | C-OP | — | — | S | Granian exposes `--static-path-dir-to-file`; tigrcorn also exposes explicit index policy controls. |
| Static expires control | C-OP | — | — | S | Granian and tigrcorn expose explicit static expiry controls. |
| TLS key / cert input | C-OP | S | S | S | All four expose basic TLS material input. |
| Encrypted key password | C-OP | S | S | S | All peers now document password-protected key support. |
| CA / client-cert verification | C-OP | S | S | S | All peers expose a public client-cert verification path. |
| Direct CRL file input | C-OP | — | — | S | tigrcorn and Granian expose direct CRL material input in the reviewed docs. |
| OCSP controls | C-OP | — | — | — | tigrcorn-only public OCSP mode/cache/soft-fail surface in this comparison. |
| ALPN controls | C-OP | — | Cfg | — | Hypercorn documents ALPN via config; tigrcorn exposes a CLI surface. |
| Proxy trust controls | C-OP | S | M | M | Hypercorn points to ProxyFixMiddleware; Granian points to proxy wrappers. |
| Custom server/date/header controls | C-OP | S | Cfg | P | Hypercorn exposes server/date behavior via config; Granian has url-path-prefix and process/log options but not the same header family. |
| Structured log / log files | C-OP | P | S | S | Uvicorn supports log config; Hypercorn and Granian expose richer file-oriented logging surfaces. |
| Metrics / StatsD / OTel | C-OP | — | S | S | Hypercorn documents StatsD; Granian documents Prometheus metrics. |
| Timeouts / concurrency limits | C-OP | S | S | S | All four expose operator-grade timeout and limit controls. |
| HTTP/1 tuning family | C-OP | P | Cfg | S | Uvicorn documents only h11 incomplete-event size; Hypercorn exposes h11 sizing in config; Granian exposes a broader H1 family. |
| HTTP/2 tuning family | C-OP | — | Cfg | S | Hypercorn exposes H2 sizing in config; Granian exposes a larger direct CLI family. |
| WebSocket size / queue / ping / compression | C-OP | S | P | P | Hypercorn documents size and ping interval; Granian documents WebSocket support but not the same full CLI family in the reviewed excerpt. |
| Alt-Svc controls | C-OP | — | Cfg | — | Hypercorn exposes config-based Alt-Svc headers. |
| CONNECT / trailer / content-coding policy | C-OP | — | — | — | tigrcorn-only policy family in this comparison. |

Primary peer sources:

- Uvicorn settings: `https://www.uvicorn.org/settings/`
- Hypercorn configuring/binds: `https://hypercorn.readthedocs.io/en/latest/how_to_guides/configuring.html`
- Hypercorn binds: `https://hypercorn.readthedocs.io/en/latest/how_to_guides/binds.html`
- Granian README / CLI help excerpt: `https://github.com/emmett-framework/granian`
