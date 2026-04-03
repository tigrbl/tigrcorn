# Feature register

Date: 2026-04-03

This is the mutable working register of current Tigrcorn feature targets and candidate target waves. It inventories what the package supports now without widening the authoritative boundary.

Canonical boundary and support sources:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/CLI_FLAG_SURFACE.md`
- `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md`
- `docs/ops/cli.md`
- `docs/ops/public.md`

## Current supported RFC and standards targets

| standards family | current targets | evidence posture |
|---|---|---|
| IETF RFC targets | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 7541, RFC 9204, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 8446, RFC 9110 Section 9.3.6, RFC 9110 Section 6.5, RFC 9110 Section 8, RFC 7232, RFC 7233, RFC 8297, RFC 7838 Section 3, RFC 5280, RFC 6960, RFC 7301 | canonical per-RFC evidence tier is declared in `docs/review/conformance/certification_boundary.json` |
| W3C targets | no current certified W3C standards targets | explicit candidate posture only for Trace Context, Server Timing, NEL, and Reporting API fields |
| registry-aligned standards work | IANA HTTP Field Name Registry and its Structured Type metadata | candidate in-bound work for RFC 9651 and field-behavior audits |

## Current supported protocol targets

| target family | current posture | notes |
|---|---|---|
| HTTP/1.1 | current supported protocol target | package-owned server surface |
| HTTP/2 | current supported protocol target | includes cleartext and TLS profiles |
| HTTP/3 | current supported protocol target | package-owned QUIC plus HTTP/3 path |
| QUIC | current supported protocol target | RFC 9000, RFC 9001, RFC 9002 posture |
| TLS 1.3 | current supported protocol target | package-owned TLS stack remains the primary claim surface |
| WebSocket over HTTP/1.1 | current supported protocol target | RFC 6455 |
| WebSocket over HTTP/2 | current supported protocol target | RFC 8441 |
| WebSocket over HTTP/3 | current supported protocol target | RFC 9220 |
| CONNECT relay | current supported protocol target | bounded to current RFC 9110 Section 9.3.6 surface |
| trailers | current supported protocol target | bounded to current RFC 9110 Section 6.5 surface |
| content coding | current supported protocol target | bounded to current RFC 9110 Section 8 surface |
| conditional requests | current supported protocol target | RFC 7232 |
| byte ranges | current supported protocol target | RFC 7233 |
| early hints | current supported protocol target | RFC 8297 |
| Alt-Svc advertisement | current supported protocol target | RFC 7838 Section 3 |

## Current supported CLI targets

| target family | current supported targets | notes |
|---|---|---|
| command surfaces | `tigrcorn`, `python -m tigrcorn`, `tigrcorn-interop` | public CLI contract |
| app and process controls | app import/factory loading, reload, workers, runtime, PID and max-request controls, config source controls, lifespan | public operator CLI surface |
| listener and binding controls | TCP, UDP, Unix, pipe, inproc, FD, endpoint, QUIC bind, ownership and backlog controls | includes hybrid RFC and pure-operator surfaces |
| TLS and security controls | cert/key material, client certs, ALPN, OCSP, CRL, revocation fetch, proxy header and default header controls | current TLS/operator surface |
| logging and observability controls | log level, access/error logs, structured logs, metrics, StatsD, OTEL endpoint | public operator CLI surface |
| resource and concurrency controls | timeouts, body/header limits, HTTP/1.1 and HTTP/2 controls, scheduler limits, WebSocket limits | public operator CLI surface |
| protocol and transport controls | HTTP version flags, protocol enablement, WebSocket compression, CONNECT, trailers, content coding, Alt-Svc, QUIC retry/0-RTT controls, pipe mode | current protocol CLI surface |
| static delivery controls | mounted route, directory-to-file behavior, index file, cache TTL | public delivery/operator surface |

## Current public operator surface targets

| target family | current supported targets | notes |
|---|---|---|
| entrypoints | `tigrcorn.run`, `tigrcorn.serve`, `tigrcorn.serve_import_string` | public runtime startup APIs |
| embedder and server objects | `tigrcorn.EmbeddedServer`, `tigrcorn.server.TigrCornServer` | explicit lifecycle control |
| static delivery APIs | `tigrcorn.StaticFilesApp`, `tigrcorn.static.mount_static_app`, `tigrcorn.static.normalize_static_route` | package-owned delivery helpers |
| config surfaces | `build_config`, `build_config_from_namespace`, `build_config_from_sources`, `config_to_dict`, `load_env_config`, `load_config_file` | public configuration contract |
| release and promotion evaluators | `evaluate_release_gates`, `evaluate_promotion_target`, `assert_release_ready`, `assert_promotion_target_ready` | public maintainer/operator evaluator surface |
| runtime modes | `auto`, `asyncio`, `uvloop` | current publicly supported runtime contract |

## Current extension surface targets

| target family | current supported targets | notes |
|---|---|---|
| optional dependency extras | `config-yaml`, `compression`, `runtime-uvloop`, `full-featured`, `certification`, `dev` | publicly supported extras |
| declared but not supported | `runtime-trio` | declared dependency path only; not current public runtime support |
| custom operator transports | `pipe`, `inproc`, `rawframed`, `custom` | public operator surface, but outside the strict RFC-certified surface where boundary docs say so |
| peer-certification tooling | `aioquic`, `h2`, `websockets`, `wsproto`, planned `sf-http` dev dependency for structured-fields comparison | tooling and evidence surface, not an implicit boundary expansion |

## Ordered candidate target queue

| order | target family | current scope posture | reason |
|---|---|---|---|
| 1 | WS/H1 plus WSS closure | in-bounds hardening candidate | mature, core, already within boundary |
| 2 | WS/H2 plus WS/H3 closure | in-bounds hardening candidate | standards are stable and map cleanly to current HTTP/2 and HTTP/3 work |
| 3 | SSE hardening | cross-repo or boundary-review candidate | useful adjacent surface, but not a current certified package target |
| 4 | QUIC/H3 state plus observability closure | in-bounds hardening candidate | required before any honest WebTransport target |
| 5 | WebTransport-H3 session plus streams plus datagrams | boundary-expansion candidate | next transport-family target only after QUIC/H3 closure and boundary review |
| 6 | WT protocol negotiation plus RFC 9651 synchronization | boundary-expansion candidate | negotiation and claims hygiene work for a future WebTransport program |
| 7 | WT/H2 fallback | boundary-expansion candidate | optional only if TCP fallback is intentionally brought into scope |

## Current in-bound candidate hardening slices

| slice | current scope posture | current target summary |
|---|---|---|
| TLS peer closure | in-bounds candidate | RFC 8446 hardening, OpenSSL 3.5+ peer interop, bounded stdlib fallback control, independent-certification evidence |
| structured fields | in-bounds candidate | RFC 9651 baseline, RFC 8941 obsoletion hygiene, `sf-http` comparison |
| field behavior | in-bounds candidate | package-owned default field presence, obsoleted-field absence, termination and forwarding behavior |
| defaults and profiles | in-bounds candidate | reviewed defaults, profile-effective defaults, flag truth, deployment profiles |
| observability | in-bounds candidate | QUIC/H3 counters, export surfaces, negative corpora, preserved evidence bundles |
