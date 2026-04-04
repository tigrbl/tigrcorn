# Feature register

Date: 2026-04-04

This is the mutable working register of current Tigrcorn feature targets and candidate target waves. It inventories what the package supports now without widening the authoritative boundary.

Claim posture used in this register:

- `implementation claim` — implemented and shipped package surface
- `architectural claim` — architecture-level naming or role used to describe the package design
- `design claim` — selected future design target that is not yet a shipped implementation claim

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

| target family | current supported targets | claim posture | notes |
|---|---|---|---|
| entrypoints | `tigrcorn.run`, `tigrcorn.serve`, `tigrcorn.serve_import_string` | implementation claim | public runtime startup APIs |
| embedder and server objects | `tigrcorn.EmbeddedServer`, architectural server object `TigrcornServer` implemented today by `tigrcorn.server.TigrCornServer` | implementation claim plus architectural claim | explicit lifecycle control |
| static delivery APIs | `tigrcorn.StaticFilesApp`, `tigrcorn.static.mount_static_app`, `tigrcorn.static.normalize_static_route` | implementation claim | package-owned delivery helpers |
| config surfaces | `build_config`, `build_config_from_namespace`, `build_config_from_sources`, `config_to_dict`, `load_env_config`, `load_config_file` | implementation claim | public configuration contract |
| release and promotion evaluators | `evaluate_release_gates`, `evaluate_promotion_target`, `assert_release_ready`, `assert_promotion_target_ready` | implementation claim | public maintainer/operator evaluator surface |
| runtime modes | `auto`, `asyncio`, `uvloop` | implementation claim | current publicly supported runtime contract |

## Current extension surface targets

| target family | current supported targets | claim posture | notes |
|---|---|---|---|
| optional dependency extras | `config-yaml`, `compression`, `runtime-uvloop`, `full-featured`, `certification`, `dev` | implementation claim | publicly supported extras |
| declared but not supported | `runtime-trio` | design claim only | declared dependency path only; not current public runtime support |
| custom operator transports | `pipe`, `inproc`, `rawframed`, `custom` | implementation claim | public operator surface, but outside the strict RFC-certified surface where boundary docs say so |
| peer-certification tooling | `aioquic`, `h2`, `websockets`, `wsproto`, planned `sf-http` dev dependency for structured-fields comparison | design claim plus tooling inventory | tooling and evidence surface, not an implicit boundary expansion |

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

| slice | current scope posture | claim posture | current target summary |
|---|---|---|---|
| TLS peer closure | in-bounds candidate | design claim | RFC 8446 hardening, OpenSSL 3.5+ peer interop, bounded stdlib fallback control, independent-certification evidence |
| structured fields | in-bounds candidate | design claim | RFC 9651 baseline, RFC 8941 obsoletion hygiene, `sf-http` comparison |
| field behavior | in-bounds candidate | design claim | package-owned default field presence, obsoleted-field absence, termination and forwarding behavior |
| defaults and profiles | in-bounds candidate | design claim | reviewed defaults, profile-effective defaults, flag truth, deployment profiles |
| observability | in-bounds candidate | design claim | QUIC/H3 counters, export surfaces, negative corpora, preserved evidence bundles |

## Roadmap-derived candidate feature register

These rows map the current roadmap bands into the mutable working register. They are candidate targets, not current implemented claims.

| feature_id | band | feature row | target family | current posture | next deliverables | evidence or conformance focus |
|---|---|---|---|---|---|---|
| `F-P1-DEFAULT-BASELINE` | `P1` | `default` safe baseline | profiles and safe baseline | in-bounds candidate | `profiles/default.profile.json`, operator docs, default audit rows | import-from-CWD, proxy spoof denial, no CONNECT relay, no early data |
| `F-P1-STRICT-H1-ORIGIN` | `P1` | `strict-h1-origin` | profiles and safe baseline | in-bounds candidate | profile spec, operator page, cert bundle | keepalive semantics, forwarded rejection, redirect-host safety |
| `F-P1-STRICT-H2-ORIGIN` | `P1` | `strict-h2-origin` | profiles and safe baseline | in-bounds candidate | profile spec, operator page, cert bundle | H2 parity, SETTINGS bounds, frame/header resource caps |
| `F-P1-STRICT-H3-EDGE` | `P1` | `strict-h3-edge` | profiles and safe baseline | in-bounds candidate | profile spec, operator page, cert bundle | token integrity, Retry path, default 0-RTT rejection, H3/QPACK stress |
| `F-P1-STRICT-MTLS-ORIGIN` | `P1` | `strict-mtls-origin` | profiles and safe baseline | in-bounds candidate | profile spec, operator page, cert bundle | cert-path validation, SAN/EKU rejection, CRL/OCSP behavior |
| `F-P1-STATIC-ORIGIN` | `P1` | `static-origin` | profiles and safe baseline | in-bounds candidate | profile spec, operator page, cert bundle | traversal denial, HEAD/GET parity, Range/If-Range correctness |
| `F-P2-BASE-DEFAULT-AUDIT` | `P2` | Base default audit | defaults and profiles | in-bounds candidate | `DEFAULT_AUDIT.json`, `DEFAULT_AUDIT.md` | post-normalization parity, three-state default tests |
| `F-P2-PROFILE-DEFAULT-AUDIT` | `P2` | Profile-effective default audit | defaults and profiles | in-bounds candidate | `PROFILE_DEFAULTS/*.json`, `PROFILE_DEFAULTS/*.md`, inheritance manifest | overlay parity, unsafe-default denial, profile doc/runtime sync |
| `F-P2-FLAG-CONTRACT-REGISTRY` | `P2` | Reviewed flag contract registry | defaults and profiles | in-bounds candidate | reviewed `flag_contracts.json` | flag review coverage, doc/runtime/help sync |
| `F-P3-PROXY-TRUST` | `P3` | Proxy trust model | proxy and public policy closure | in-bounds candidate | normative proxy contract | spoofed chain rejection, mixed-trust rejection |
| `F-P3-PROXY-PRECEDENCE` | `P3` | Proxy precedence plus normalization | proxy and public policy closure | in-bounds candidate | precedence tables, normalization contract | conflicting host/proto/port tests, root-path injection tests |
| `F-P3-CONNECT-POLICY` | `P3` | CONNECT relay policy | proxy and public policy closure | in-bounds candidate | policy docs, attack corpus slice | open-proxy denial, loopback/private-IP denial, DNS rebinding |
| `F-P3-TRAILER-POLICY` | `P3` | Trailer policy | proxy and public policy closure | in-bounds candidate | policy docs, flag metadata | trailer correctness and malformed-trailer negatives |
| `F-P3-CODING-POLICY` | `P3` | Content-coding policy | proxy and public policy closure | in-bounds candidate | policy docs, origin hooks | coding negotiation, compressed-range behavior |
| `F-P3-PUBLIC-CONTROLS` | `P3` | ALPN/revocation/H2C/WS compression/limits/drain | proxy and public policy closure | in-bounds candidate | CLI/help/docs, policy metadata, operator pages | ALPN, OCSP/CRL, H2C, WS compression, idle/limit/drain tests |
| `F-P4-EARLY-DATA-ADMISSION` | `P4` | Early-data admission policy | QUIC semantic closure | in-bounds candidate | early-data contract | admission matrix, unsafe-method rejection |
| `F-P4-REPLAY-POLICY` | `P4` | Replay policy | QUIC semantic closure | in-bounds candidate | replay policy spec | replay behavior, `425` retry, intermediary propagation |
| `F-P4-MULTI-INSTANCE-EARLY-DATA` | `P4` | Multi-instance early-data policy | QUIC semantic closure | in-bounds candidate | topology policy, deployment notes | multi-node replay, shared-ticket edge cases |
| `F-P4-RETRY-APP-VISIBILITY` | `P4` | Retry plus app-visible semantics | QUIC semantic closure | in-bounds candidate | Retry/0-RTT interaction spec, runtime contract | invalid Retry, duplicate Retry, app visibility consistency |
| `F-P4-INDEPENDENT-QUIC-CLAIMS` | `P4` | Independent QUIC state claims | QUIC semantic closure | in-bounds candidate | profile bindings, operator docs | token integrity, migration spoofing, GOAWAY/QPACK stress |
| `F-P5-PATH-RESOLUTION` | `P5` | Path resolution | origin delivery contract | in-bounds candidate | normative origin contract | traversal, encoded traversal, symlink escape |
| `F-P5-FILE-SELECTION-HTTP` | `P5` | File selection plus HTTP semantics | origin delivery contract | in-bounds candidate | origin contract, conformance corpus | HEAD parity, conditional conflicts, range-past-EOF |
| `F-P5-PATHSEND-CONTRACT` | `P5` | ASGI `pathsend` contract | origin delivery contract | in-bounds candidate | origin contract, operator docs | file-replaced-mid-send, partial-send, disconnect-race |
| `F-P6-QUIC-H3-COUNTERS` | `P6` | QUIC/H3 counter families | observability | in-bounds candidate | metrics schema, operator docs | counter correctness under retry, migration, loss |
| `F-P6-EXPORT-SURFACES` | `P6` | Export surfaces | observability | in-bounds candidate | export config/docs | export smoke, schema compatibility |
| `F-P6-QLOG-STANCE` | `P6` | qlog experimental stance | observability | in-bounds candidate | experimental export spec, schema versioning | redaction, schema-version, trace integrity |
| `F-P7-FAIL-STATE-REGISTRY` | `P7` | Fail-state registry | negative certification | in-bounds candidate | negative-cert registry | assertion coverage |
| `F-P7-NEGATIVE-CORPORA-QUIC` | `P7` | Proxy/early-data/QUIC corpora | negative certification | in-bounds candidate | attack corpora, expected outcomes | negative suites with preserved evidence |
| `F-P7-NEGATIVE-CORPORA-ORIGIN` | `P7` | Origin/CONNECT/TLS/topology corpora | negative certification | in-bounds candidate | corpora, expected outcomes, evidence bundles | traversal, open relay, wrong EKU/SAN, mixed topology |
| `F-P8-RISK-TRACEABILITY` | `P8` | Risk register plus traceability | governance and promotion discipline | in-bounds candidate | `RISK_REGISTER*`, `RISK_TRACEABILITY.json`, schema/docs | schema, ID uniqueness, referential integrity |
| `F-P8-PYTEST-FORWARD` | `P8` | Pytest-only forward motion | governance and promotion discipline | in-bounds candidate | `TEST_STYLE_POLICY.md`, `LEGACY_UNITTEST_INVENTORY.json` | no new unittest imports/classes, mirror-exists tests |
| `F-P8-RELEASE-GATED-EVIDENCE` | `P8` | Release-gated evidence plus interop plus perf | governance and promotion discipline | in-bounds candidate | boundary manifests, interop bundles, perf bundles | release-gate suite, artifact retention checks |
| `F-P8-RFC9651-BASELINE` | `P8` | RFC 9651 structured-fields baseline | structured fields | in-bounds candidate | SFV conformance tests, dependency review, claim sync | round-trip/canonical serialization, stale-reference lint |

## Atomic TLS / HTTPS interop claim rows

If the TLS peer-closure slice is opened, register and execute it as atomic RFC rows rather than broad umbrella statements.

| RFC target | subfeature requirement | execution posture | priority |
|---|---|---|---|
| RFC 8446 | protected record outer framing | immediate custom-TLS fault-domain target; anchor on OpenSSL `bad record type` reproduction | `P0` |
| RFC 8446 | inner content type recovery | immediate custom-TLS fault-domain target; pair with decrypt/reparse fixtures | `P0` |
| RFC 8446 | AEAD additional data construction | immediate transcript parity target; verify against strict peer failures | `P0` |
| RFC 8446 | padding semantics | immediate record-layer target; include edge-case padding corpus | `P0` |
| RFC 8446 | handshake-to-application-data boundary | immediate state-transition target; verify first encrypted app-data record timing | `P0` |
| RFC 8446 | alert emission and close semantics | follow-on TLS behavior target after record-layer stabilization | `P1` |
| RFC 8446 | Certificate and CertificateVerify processing | follow-on handshake-message target for external peer success/failure parity | `P1` |
| RFC 7301 | ALPN negotiation policy | follow-on H1/H2 negotiation target linked to `#21` | `P1` |
| RFC 6066 | SNI handling | follow-on certificate-selection and hostname-routing target | `P1` |
| RFC 6066 | OCSP stapling request handling | explicit support/deny/policy gate target; avoid ambiguous behavior | `P2` |
| RFC 5280 | AKI/SKI handling | immediate cert-profile target for modern verifier acceptance | `P0` |
| RFC 5280 | KeyUsage / ExtendedKeyUsage correctness | immediate cert-profile target for server-auth and mTLS honesty | `P0` |
| RFC 5280 | path validation correctness | immediate peer-validation target; chain-building and issuer-linkage correctness | `P0` |
| RFC 6960 | OCSP policy | explicit hard-fail/soft-fail policy target if OCSP rows are opened | `P2` |
| RFC 9525 | service identity / hostname verification compatibility | follow-on HTTPS interop target for SAN and DNS-ID correctness | `P1` |
| RFC 9112 | HTTPS over HTTP/1.1 interoperability | promote only after TLS row stability; use curl/OpenSSL read success as evidence | `P1` |
| RFC 9113 | HTTP/2 over TLS posture | promote only after TLS plus ALPN stability; require explicit H2 negotiation evidence | `P2` |
| RFC 9001 | QUIC-TLS mapping parity | sequence after TCP/TLS row closure; keep QUIC mapping honest | `P2` |
| RFC 9000 | Retry/token integrity dependencies on TLS-derived state | sequence after TLS transcript stabilization | `P2` |
| RFC 9114 | HTTP/3 control-plane correctness dependent on TLS success | hold until external-peer QUIC handshakes are reproducible | `P3` |
| RFC 9204 | QPACK pressure/error handling after H3 establishment | hold until H3 handshakes are stable | `P3` |

## TLS / HTTPS interop peer roles

| peer | role | evidence posture |
|---|---|---|
| OpenSSL 3.5+ | strict external TLS peer | `independent_certification` |
| curl linked against OpenSSL 3.5+ | external HTTPS application peer | `independent_certification` |
| Python stdlib `ssl` | bounded differential oracle | not an evidence-tier upgrade |
| Tigrcorn internal TLS driver | same-stack replay peer | `same_stack_replay` only |
