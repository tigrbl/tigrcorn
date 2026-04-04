# Tigrcorn master feature target matrix

Date: 2026-04-04

This note consolidates the current Tigrcorn target posture with the future target waves proposed across the external planning inputs:

- `./tigrcorn_master_feature_target_matrix.md`
- `./tigrcorn_additional_claims_registration_matrix.md`
- `./structured-fields-rfc9651-target-matrix.md`
- `./http_fields_and_standards_boundary_matrices.md`
- `./tigrcorn_tls_rfc_targets_and_openssl35_t4_plan.md`
- `./tigrbl_tigrcorn_protocol_semantic_expansion_plan.md`
- `./tigrbl_tigrcorn_full_architecture_handoff.md`

This note does not widen the current package boundary. The authoritative in-bounds and out-of-bounds policy remains:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

## Claim posture legend

Use these labels when reading or extending this matrix:

- `implementation claim` — implemented and shipped package surface
- `architectural claim` — architecture-level naming or role used to describe the package design
- `design claim` — selected future design target that is not yet a shipped implementation claim

## Current target posture

The current `0.3.9` repository line is already green for:

- authoritative boundary
- strict target under the canonical `0.3.9` release root
- promotion target

There are no open in-bounds certification blockers in `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md`.

That means the current targets are limited to:

1. preserve code, docs, tests, and machine-readable parity for the current T/P/A/D/R boundary
2. accept only patch-level in-bound maintenance unless the boundary is intentionally expanded first
3. keep explicit non-goals out of the active implementation queue until policy docs change

## Master matrix

| wave | status_now | target family | scope posture | primary targets | source basis | prerequisite before execution |
|---|---|---|---|---|---|---|
| Current | active | Current-line maintenance | in-bounds now | keep `0.3.9` green; preserve release-gate parity; maintain current operator/docs/evidence alignment | current repo state and current-state chain | none beyond normal patch discipline |
| Wave 1 | candidate | In-bound hardening bundle | in-bounds candidate | deployment profiles; default audits; proxy policy closure; ALPN/revocation controls; early-data semantics; origin/static/pathsend contract | external master matrix `P1`-`P5` plus claims matrix | select explicit subset and convert into repo backlog entries |
| Wave 2 | candidate | In-bound field and observability bundle | in-bounds candidate | RFC 9651 structured-fields closure; HTTP field presence/absence/termination audits; QUIC/H3 counters; export surfaces; negative certification corpora; risk/register traceability; release-gated perf/evidence discipline | external master matrix `P6`-`P8`; structured-fields matrix; HTTP fields matrix | confirm each item stays inside T/P/A/D/R and does not change public claims unintentionally |
| Wave 3 | blocked by policy | Boundary-expansion RFC wave | out-of-bounds now | RFC 9218; RFC 9111; RFC 9530; RFC 9421; JOSE/COSE-adjacent surfaces | boundary non-goals and external expansion planning | update boundary docs first; minor-version decision |
| Wave 4 | blocked by policy | Runtime/pluggability expansion wave | out-of-bounds now | Trio runtime support; parser/backend pluggability; WebSocket engine pluggability; alternate interface families | boundary non-goals and external expansion planning | update boundary docs first; minor-version decision |
| Wave 5 | cross-repo future | Tigrbl plus Tigrcorn semantic expansion | not a current Tigrcorn package target | SSE/HTTP stream/WebTransport semantic binding model; `OpChannel`; exchange/family/subevent runtime model; alias and runtime-kernel expansion | protocol semantic expansion plan and architecture handoff | separate cross-repo program and explicit package-boundary review |

## Current targets detail

| target | current state | notes |
|---|---|---|
| authoritative boundary | green | canonical package claim is already satisfied |
| strict target | green | satisfied under `docs/review/conformance/releases/0.3.9/release-0.3.9/` |
| promotion target | green | no open promotion blockers |
| in-bounds backlog | complete | `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md` reports no open in-bounds blockers |
| allowed new work | maintenance only by default | patch-level operator/docs/evidence repairs remain acceptable |

## Current supported targets inventory

These are the current support families that should be treated as active inventory, not future expansion:

| family | current supported targets | claim posture | canonical sources |
|---|---|---|---|
| RFC / IETF targets | RFC 9112, RFC 9113, RFC 9114, RFC 9000, RFC 9001, RFC 9002, RFC 7541, RFC 9204, RFC 6455, RFC 7692, RFC 8441, RFC 9220, RFC 8446, RFC 9110 Section 9.3.6, RFC 9110 Section 6.5, RFC 9110 Section 8, RFC 7232, RFC 7233, RFC 8297, RFC 7838 Section 3, RFC 5280, RFC 6960, RFC 7301 | implementation claim | `docs/review/conformance/certification_boundary.json` |
| protocol targets | HTTP/1.1, HTTP/2, HTTP/3, QUIC, TLS 1.3, WebSocket over HTTP/1.1, WebSocket over HTTP/2, WebSocket over HTTP/3, CONNECT relay, trailers, content coding, Alt-Svc advertisement, conditional requests, byte ranges, early hints | implementation claim | `README.md`; `docs/protocols/*.md`; `docs/review/conformance/CERTIFICATION_BOUNDARY.md` |
| CLI targets | `tigrcorn`, `python -m tigrcorn`, `tigrcorn-interop`; public command families for app/process, listeners, static delivery, TLS/security, logging/observability, resources/timeouts/concurrency, protocol/transport | implementation claim | `docs/ops/cli.md`; `docs/review/conformance/CLI_FLAG_SURFACE.md` |
| public operator surface targets | `run`, `serve`, `serve_import_string`, `EmbeddedServer`, `StaticFilesApp`, `mount_static_app`, `normalize_static_route`, config builders/loaders, release/promotion evaluators, architectural server object `TigrcornServer` implemented today by `tigrcorn.server.TigrCornServer` | implementation claim plus architectural claim | `docs/ops/public.md` |
| extension surface targets | `config-yaml`, `compression`, `runtime-uvloop`, `full-featured`, `certification`, `dev`; public custom transport/operator surfaces `pipe`, `inproc`, `rawframed`, `custom` where already documented | implementation claim | `docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md`; `docs/ops/cli.md` |
| W3C targets | no current certified W3C standards claims; only explicit posture work for `traceparent`, `tracestate`, `Server-Timing`, `NEL`, and `Reporting-Endpoints` as candidate field-behavior inventory items | design claim only | `docs/notes/feat_matrix.md`; `docs/review/conformance/BOUNDARY_NON_GOALS.md` |

## Future target waves

### Wave 1: in-bound hardening and deployment posture

Use this wave only if the repo chooses more in-bound work after `0.3.9`.

| bundle | candidate targets | package-boundary fit |
|---|---|---|
| Profiles and safe baseline | `default`, `strict-h1-origin`, `strict-h2-origin`, `strict-h3-edge`, `strict-mtls-origin`, `static-origin` | fits current T/P/A/D/R boundary |
| Default and flag truth | reviewed defaults, profile-effective defaults, normalized flag-contract truth | fits current operator/governance surface |
| Proxy and public policy closure | proxy precedence, CONNECT/trailer/content-coding policy, ALPN control, revocation control, limits/timeouts | fits current protocol/operator surface if kept package-owned |
| TCP/TLS interop and differential control | RFC 8446 record-layer hardening for the custom TLS stack, bounded `--ssl-backend=stdlib` fallback, OpenSSL 3.5+ `s_client` and curl/OpenSSL peer harnesses, SNI/ALPN/service-identity verification | fits current package-owned transport/security boundary if the custom TLS stack remains the primary certified implementation |
| Early-data and QUIC semantics | Retry, 0-RTT, replay posture, migration/resumption semantics | fits current QUIC/TLS/runtime boundary |
| Origin delivery contract | path resolution, file selection, validators, range semantics, `pathsend` contract | fits current delivery/origin boundary |

### Wave 2: in-bound evidence and observability hardening

| bundle | candidate targets | package-boundary fit |
|---|---|---|
| Structured fields baseline | RFC 9651 as the sole active structured-fields baseline; explicit obsoletion of RFC 8941 in repo docs, claims, and evidence; registry-aware structured type handling; deterministic serialization; malformed-field negative corpus | fits current protocol/governance surface when scoped to field parsing/serialization only |
| Field-domain audit and default field posture | confirm default presence of package-owned fields; confirm obsoleted fields are absent by default; confirm default termination behavior for connection-scoped and hop-by-hop fields; document standards ownership by field family | fits current transport/protocol/delivery/runtime surface when limited to package-owned fields |
| TLS peer-certification program | OpenSSL 3.5+ external peer harness, curl/OpenSSL peer rows, preserved stderr/stdout artifacts, negative corpus against strict external peers | fits current certification/evidence surface and strengthens the package-owned TCP/TLS claim |
| Observability | QUIC/H3 counters, structured logs, telemetry exports, experimental qlog stance | fits current operator surface if claim language stays bounded |
| Negative certification | proxy, early-data, QUIC, origin, CONNECT, TLS/X.509 negative corpora | fits current certification/evidence surface |
| Governance and release discipline | risk register, traceability, preserved interop bundles, perf artifact discipline, structured-fields hygiene | fits current governance/release surface |

### Ordered protocol-family queue

This is the ordered future feature queue requested for protocol-family selection. It does not override the boundary; items that exceed the current package claim remain policy-blocked until the boundary changes first.

| order | target family | reason | current scope posture |
|---|---|---|---|
| 1 | WS/H1 plus WSS closure | mature, core, already within boundary | in-bounds hardening candidate |
| 2 | WS/H2 plus WS/H3 closure | standards are stable and map cleanly to current HTTP/2 and HTTP/3 work | in-bounds hardening candidate |
| 3 | SSE hardening | cheap surface-area expansion with strong utility | cross-repo or boundary-review candidate, not a current certified package target |
| 4 | QUIC/H3 state plus observability closure | required before any honest WebTransport target | in-bounds hardening candidate |
| 5 | WebTransport-H3 session plus streams plus datagrams | natural next transport-family target once QUIC/H3 is certifiable | boundary-expansion candidate |
| 6 | WT protocol negotiation plus RFC 9651 synchronization | required for clean negotiation and claims hygiene | boundary-expansion candidate |
| 7 | WT/H2 fallback | optional only if TCP fallback is intentionally brought into scope | boundary-expansion candidate |

### Wave 1A: TLS RFC and OpenSSL 3.5+ targets

This slice keeps the custom pure-Python TLS 1.3 stack as the primary certified implementation and uses OpenSSL 3.5+ as an external peer oracle.

| target | standards references | candidate target |
|---|---|---|
| Custom TLS stays primary | RFC 8446; current certification boundary | keep the package-owned custom TLS 1.3 implementation as the primary code path and claim surface for TCP/TLS listeners |
| Bounded stdlib fallback | implementation control, not a boundary expansion | add `--ssl-backend=stdlib` as an operator fallback and differential control without replacing the package-owned TLS claim |
| RFC 8446 record-layer hardening | RFC 8446 | verify `TLSCiphertext`, AEAD additional data, `TLSInnerPlaintext.type`, padding, record length, key-change boundaries, and alert framing against strict external peers |
| Record-size handling | RFC 8446; RFC 8449 | close record-size and padding accounting behavior where implemented |
| SNI and extension interop | RFC 6066 | verify `server_name` and adjacent TLS extension behavior against OpenSSL peers |
| ALPN interop | RFC 7301 | verify `http/1.1` and `h2` negotiation behavior when exposed |
| Certificate and service identity | RFC 5280; RFC 9525 | verify chain validity, SAN/EKU/AKI/SKI expectations, and hostname verification semantics with external peers |
| OCSP and revocation | RFC 6960 | keep peer validation scoped to claimed OCSP/revocation surfaces only |
| Independent peer harness | OpenSSL 3.5+ `s_client`; curl with OpenSSL backend 3.5+ | add preserved external peer evidence for TCP/TLS handshake and HTTPS response success under `independent_certification` |
| Tier mapping discipline | current certification evidence tiers | keep the canonical evidence tiers as `local_conformance`, `same_stack_replay`, and `independent_certification`; do not invent a fourth tier |

#### Atomic RFC target matrix for the current TLS / HTTPS interop lane

Use this matrix when decomposing the Wave 1A TLS slice into claim-registration rows. One row equals one RFC target plus one concrete subfeature requirement so promotion-facing statements stay atomic and evidenceable.

| RFC target | subfeature requirement | Tigrcorn implementation target | required evidence / tests | priority |
|---|---|---|---|---|
| RFC 8446 | TLS 1.3 protected record outer framing | `TLSCiphertext` records emitted with correct outer content type, legacy record version handling, and length accounting | OpenSSL 3.5+ `s_client` read-path probe; byte-level record fixture tests; negative malformed-length tests | `P0` |
| RFC 8446 | TLS 1.3 inner content type recovery | `TLSInnerPlaintext` encodes the correct inner content type and permits correct post-decrypt recovery by strict peers | OpenSSL 3.5+ interop; custom decrypt/reparse fixtures; negative wrong-inner-type tests | `P0` |
| RFC 8446 | TLS 1.3 padding semantics | zero-padding handling for protected records is correct and non-ambiguous to external peers | OpenSSL 3.5+ probe with padded application records; padding edge-case corpus | `P0` |
| RFC 8446 | TLS 1.3 AEAD additional data construction | additional authenticated data matches the protected record header semantics expected by peers exactly | cross-check against stdlib and OpenSSL transcript behavior; tamper/failure negative corpus | `P0` |
| RFC 8446 | handshake-to-application-data boundary | key change timing after `Finished` is exact; first encrypted application record is emitted under the correct traffic keys | `curl` and `s_client` handshake-then-read tests; transcript/state-transition assertions | `P0` |
| RFC 8446 | alert emission and close semantics | fatal alerts, `close_notify` behavior, and post-failure shutdown are spec-correct and externally intelligible | OpenSSL alert-path tests; negative cert/path tests; preserved stderr/stdout artifacts | `P1` |
| RFC 8446 | Certificate and CertificateVerify processing | certificate message flow, signature algorithm negotiation, and certificate verify behavior interoperate with external peers | OpenSSL 3.5+ success/failure handshakes; cert-chain variant corpus | `P1` |
| RFC 7301 | ALPN negotiation policy | ALPN offer, selection, and denial are explicit and externally testable for H1/H2 lanes | `s_client -alpn`; `curl --http1.1`; H2 negotiation tests | `P1` |
| RFC 6066 | SNI handling | Server Name Indication handling is correct for hostname-based TLS identity and certificate selection | `s_client -servername`; hostname/cert-switch tests | `P1` |
| RFC 6066 | OCSP stapling request handling | `status_request` behavior is explicitly supported, denied, or policy-gated rather than ambiguous | `s_client -status`; stapled vs unstapled evidence bundles | `P2` |
| RFC 5280 | Authority Key Identifier / Subject Key Identifier handling | demo and certification cert chains include extension material needed for modern verifier acceptance | OpenSSL path-validation corpus; clean-room cert-generation tests | `P0` |
| RFC 5280 | KeyUsage / ExtendedKeyUsage correctness | leaf and intermediate certificates carry usages suitable for server auth and mTLS where claimed | negative wrong-EKU / wrong-KeyUsage tests; stdlib and OpenSSL validation evidence | `P0` |
| RFC 5280 | path validation correctness | chain building, validity interval checks, basic constraints, and issuer linkage pass strict peer validation | OpenSSL verify-path runs; preserved chain-validation bundles | `P0` |
| RFC 6960 | OCSP policy | hard-fail, soft-fail, and responder-unavailable policy is explicit and testable | stale-OCSP, unavailable-responder, hard/soft-fail corpus | `P2` |
| RFC 9525 | service identity / hostname verification compatibility | certificates used for public HTTPS interop satisfy modern DNS-ID and SAN-based identity expectations | `curl --cacert` hostname validation; mismatch negative tests | `P1` |
| RFC 9112 | HTTPS over HTTP/1.1 interoperability | once TLS succeeds, HTTPS/H1 response semantics remain stable for external clients | `curl --http1.1` success matrix; response/read-body smoke tests | `P1` |
| RFC 9113 | HTTP/2 over TLS posture | if H2 is claimed, TLS plus ALPN setup supports correct H2 negotiation and rejects invalid H2C/TLS ambiguity | `curl --http2`; ALPN/H2 interop tests; SETTINGS/resource-cap tests | `P2` |
| RFC 9001 | QUIC-TLS mapping parity | custom TLS implementation used for QUIC preserves correct TLS 1.3 semantics where mapped into QUIC | QUIC handshake corpus; driver-vs-external transcript comparisons | `P2` |
| RFC 9000 | Retry/token integrity dependencies on TLS-derived state | Retry and token validation remain correct if TLS transcript/key behavior changes | malformed-token and Retry-integrity tests | `P2` |
| RFC 9114 | HTTP/3 control-plane correctness dependent on TLS success | H3 claims promote only after TLS-backed QUIC handshakes are externally reproducible | H3 peer harness; GOAWAY / decode-failure tests | `P3` |
| RFC 9204 | QPACK pressure/error handling after H3 establishment | QPACK behavior is tested only after external-peer H3 handshake stability exists | blocked-stream / decode-failure corpus | `P3` |

#### Non-RFC certification peers for the TLS / HTTPS interop lane

These peer rows sit beside the RFC matrix but are not themselves RFC claims.

| peer target | requirement | purpose |
|---|---|---|
| OpenSSL 3.5+ | treat as an `independent_certification` peer for TCP/TLS lanes | independent strict parser and verifier for custom TLS record-layer correctness |
| curl linked against OpenSSL 3.5+ | treat as an `independent_certification` application-facing peer for HTTPS H1/H2 lanes | confirms not just handshake success, but successful external client reads |
| Python stdlib `ssl` | treat as a differential oracle, not an independent-certification peer | fast local comparator to isolate custom-code divergence |
| Tigrcorn internal TLS driver | treat as a same-stack replay lane, not an independent peer | useful for development, insufficient for promotion |

### Wave 2A: RFC 9651 structured-fields targets

This slice uses RFC 9651 as the current baseline and treats RFC 8941 as obsolete.

| target | standards references | candidate target |
|---|---|---|
| Baseline switch | RFC 9651; IANA HTTP Field Name Registry Structured Type column | replace active RFC 8941 references with RFC 9651 across docs, claims, comments, and evidence |
| Explicit obsoletion handling | RFC 9651 obsoletes RFC 8941 | add reference-lint and claim-lint checks so RFC 8941 is not presented as the current baseline |
| Parser and serializer conformance | RFC 9651 | certify parser behavior, canonical serialization, duplicate handling, parameters, inner lists, dictionaries, items, byte sequences, and Date support |
| Registry-aware field classification | IANA HTTP Field Name Registry | use Structured Type metadata for known fields and preserve a reviewed registry snapshot or provenance trail |
| Peer certification dependency | `sf-http` dev dependency | use `sf-http` as a development and peer-certification comparison target for RFC 9651 parsing and serialization behavior |
| Deterministic evidence | RFC 9651 | add parse->serialize->parse round-trip tests, golden canonical-output tests, and malformed-field negative corpus bundles |

### Wave 2B: HTTP fields and trace fields targets

This slice should stay bounded to fields that Tigrcorn directly owns, normalizes, terminates, emits, or suppresses by default.

| target | standards references | candidate target |
|---|---|---|
| Default field presence audit | RFC 9110; RFC 9112; RFC 9113; RFC 9114; RFC 6455; RFC 7239; RFC 7838 Section 3; RFC 8470; RFC 7301 | confirm the default presence, absence, or suppression of package-owned fields such as `Host`, `Connection`, `Transfer-Encoding`, `Trailer`, `Upgrade`, `TE`, `Forwarded`, `Alt-Svc`, `Early-Data`, `ALPN`, `Via`, and `Sec-WebSocket-*` where applicable |
| Obsoleted field absence audit | IANA HTTP Field Name Registry; RFC-obsoleted field statuses | confirm obsoleted fields are not emitted by default and not synthesized by normalization layers; examples include `Digest`, `Want-Digest`, `Content-MD5`, `Cookie2`, `Set-Cookie2`, `HTTP2-Settings`, `Warning`, and other obsolete registry rows that are outside the current surface |
| Structured registered field handling | RFC 9651; IANA Structured Type metadata | confirm structured registered fields that Tigrcorn terminates or emits use the correct expected type and canonical behavior |
| W3C trace field posture | W3C Trace Context; Server Timing; Reporting API; NEL | define whether `traceparent`, `tracestate`, `Server-Timing`, `NEL`, and `Reporting-Endpoints` are passed through, terminated, normalized, suppressed, or emitted by default, without turning them into implicit package claims |
| Default termination behavior | RFC 9110 connection-specific field rules; RFC 9112; RFC 9113; RFC 9114; RFC 6455; W3C Trace Context | freeze the default termination, forwarding, stripping, and regeneration behavior for all package-owned field families at listener termination boundaries |
| Hop-by-hop and connection-specific safety | RFC 9110; RFC 9112 | certify stripping or bounded handling for connection-scoped fields and invalid cross-hop propagation cases |
| Protocol-carrier variance | RFC 9112; RFC 9113; RFC 9114; RFC 6455; RFC 9220 | verify field behavior across HTTP/1.1, HTTP/2, HTTP/3, WebSocket over HTTP/1.1, RFC 8441, and RFC 9220 carriers where the package owns the semantics |

### Wave 3: explicit boundary-expansion candidates

These are not current Tigrcorn obligations and must not be treated as active targets until the boundary is changed first.

| family | current status | why blocked |
|---|---|---|
| RFC 9218 prioritization | out of bounds | named non-goal |
| RFC 9111 caching/freshness | out of bounds | named non-goal |
| RFC 9530 digest fields | out of bounds | named non-goal |
| RFC 9421 signatures | out of bounds | named non-goal |
| JOSE / COSE | out of bounds | named non-goal |

The field-oriented consequences are:

- `Priority` remains a boundary-expansion target because RFC 9218 prioritization is currently out of scope
- `Content-Digest`, `Repr-Digest`, `Want-Content-Digest`, and `Want-Repr-Digest` remain conditional expansion surfaces because RFC 9530 is not in the current boundary
- signature-carrying fields such as `Signature` and `Signature-Input` remain conditional expansion surfaces because RFC 9421 is not in the current boundary
- broader cache/freshness fields such as `Cache-Control`, `Age`, `Expires`, `Vary`, `Cache-Status`, and `CDN-Cache-Control` remain outside the current Tigrcorn core claim except for the already-bounded direct-delivery/entity semantics the package currently owns

### Wave 4: runtime and pluggability expansion candidates

| family | current status | why blocked |
|---|---|---|
| Trio runtime support | out of bounds | reserved dependency path only today |
| parser/backend pluggability | out of bounds | named non-goal |
| WebSocket engine pluggability | out of bounds | named non-goal |
| ASGI2 / WSGI / RSGI families | out of bounds | named non-goal |

### Wave 5: cross-repo semantic expansion candidates

These items come from the Tigrbl plus Tigrcorn architecture notes. They are future program inputs, not current Tigrcorn package targets.

| family | examples | current posture |
|---|---|---|
| semantic binding expansion | REST, JSON-RPC/HTTP, HTTP stream, SSE, WS/WSS, JSON-RPC over WS/WSS, WebTransport, app-framed WebTransport | cross-repo design input |
| runtime model expansion | `OpChannel`, exchange templates, family/subevent derivation, `POST_EMIT` completion fences | cross-repo design input |

## Ordering rule

Future work should be selected in this order:

1. current-line maintenance
2. Wave 1 in-bound hardening
3. ordered protocol-family items that are still in-bounds, namely WS/H1 plus WSS closure, WS/H2 plus WS/H3 closure, and QUIC/H3 state plus observability closure
4. Wave 2A RFC 9651 structured-fields closure
5. Wave 2B field presence, obsoletion, and termination audits
6. Wave 2 in-bound evidence and observability
7. Wave 3 or Wave 4 only after an explicit boundary update
8. Wave 5 plus SSE or WebTransport-family items only as a separate cross-repo or boundary-expansion program with package-boundary review

## Recommendation

If a new Tigrcorn target wave is started from this repository state, the safest next selection is:

1. Wave 1 deployment profiles and default-audit closure
2. WS/H1 plus WSS closure, then WS/H2 plus WS/H3 closure
3. Wave 1 proxy and public policy closure
4. Wave 1A TLS RFC 8446 and OpenSSL 3.5+ independent-certification closure
5. QUIC/H3 state plus observability closure
6. Wave 2A RFC 9651 closure with `sf-http` peer-certification checks
7. Wave 2B package-owned field presence, obsoletion, and termination audits
8. Wave 2 negative certification and observability hardening

That sequence strengthens the current package without changing the public boundary claim.

## Field and standards references to use

When Wave 2A and Wave 2B are opened, use these references explicitly in the resulting target rows, tests, and evidence:

| family | primary references |
|---|---|
| Structured fields | RFC 9651; IANA HTTP Field Name Registry Structured Type column |
| HTTP core field semantics | RFC 9110; RFC 9112; RFC 9113; RFC 9114 |
| Conditional and range fields | RFC 7232; RFC 7233 |
| WebSocket handshake fields | RFC 6455; RFC 8441; RFC 9220 |
| Alt-Svc advertisement fields | RFC 7838 Section 3 |
| Early-Data field | RFC 8470 |
| Forwarded field | RFC 7239 |
| TLS 1.3 record and handshake behavior | RFC 8446; RFC 8449; RFC 6066 |
| ALPN field posture | RFC 7301 plus current package transport policy |
| Certificate and service identity | RFC 5280; RFC 9525; RFC 6960 when claimed |
| W3C trace fields | W3C Trace Context |
| Browser timing/reporting fields | Server Timing; NEL; Reporting API |
| CTA field families | CTA CMCD and CMSD specifications where those fields are only inventoried, not claimed |

## TLS peer-certification acceptance gates

If the TLS target slice is opened, the minimum acceptance gates should be:

1. the custom TLS stack remains the implementation under test for the package-owned TCP/TLS claim
2. `--ssl-backend=stdlib` is documented as a bounded fallback and differential control, not as the primary certified TLS implementation
3. OpenSSL 3.5+ `s_client` and curl/OpenSSL probes complete TLS 1.3 handshake, certificate verification, hostname verification, and HTTP response exchange successfully
4. disallowed failure classifications include `tls_record_layer_bad_record_type`, `tls_unexpected_message`, `tls_record_overflow`, `certificate_verification_failure`, `alpn_negotiation_failure`, and generic non-zero peer exits
5. the preserved peer artifacts are linked into `independent_certification` evidence rather than inventing a fourth evidence tier

## Default field-behavior acceptance gates

If the field-target waves are opened, the minimum acceptance gates should be:

1. field inventory exists for package-owned fields and classifies each field as emit, terminate, pass through, normalize, suppress, or reject by default
2. obsoleted fields that are outside the current surface are proven absent by default
3. package-owned connection-specific and hop-by-hop field handling is frozen across HTTP/1.1, HTTP/2, HTTP/3, and WebSocket carrier paths as applicable
4. W3C trace fields have an explicit default posture stating whether Tigrcorn terminates, forwards, regenerates, or leaves them to the hosted application
5. RFC 9651 structured-field handling is deterministic and peer-checked against `sf-http`

## Roadmap band alignment

The following roadmap rows are the explicit candidate feature matrix for future in-bounds work selection. These rows do not widen the current package boundary and do not imply that implementation has already started.

| band | roadmap theme | feature row | scope posture | what gets implemented or frozen | why it is next | primary deliverables | required conformance or evidence | roadmap status |
|---|---|---|---|---|---|---|---|---|
| `P1` | Safe deployment products | `default` safe baseline | in-bounds candidate | freeze boring safe zero-config posture for TCP plus HTTP/1.1, no proxy trust unless configured, no H2/H3/QUIC unless explicit, CONNECT denied, server header off, early data denied or N/A | reduces operator state space first | `profiles/default.profile.json`, operator docs, default audit rows | import-from-CWD, proxy spoof denial, no CONNECT relay, no early data, docs equal runtime | implement first |
| `P1` | Safe deployment products | `strict-h1-origin` | in-bounds candidate | freeze H1 origin semantics, trusted-proxy normalization, explicit static/pathsend posture | gives a reproducible conservative origin mode | profile spec, operator page, cert bundle | keepalive semantics, forwarded rejection, redirect-host safety | implement first |
| `P1` | Safe deployment products | `strict-h2-origin` | in-bounds candidate | freeze TLS plus ALPN plus H2 defaults, frame/header/window bounds, trailer/static semantics | moves H2 from ad hoc to auditable | profile spec, operator page, cert bundle | H2 parity, SETTINGS bounds, frame/header resource cap tests | implement first |
| `P1` | Safe deployment products | `strict-h3-edge` | in-bounds candidate | freeze QUIC/H3 listener policy, Retry, migration, resumption, Alt-Svc posture, deny-by-default 0-RTT | turns H3 from flag soup into an operating mode | profile spec, operator page, cert bundle | token integrity, Retry path, 0-RTT rejected by default, H3/QPACK stress | implement first |
| `P1` | Safe deployment products | `strict-mtls-origin` | in-bounds candidate | freeze client-cert requirement, SAN/EKU policy, revocation mode, hard/soft fail behavior | converts mTLS support into a repeatable posture | profile spec, operator page, cert bundle | cert-path validation, SAN/EKU rejection, CRL/OCSP behavior | implement first |
| `P1` | Safe deployment products | `static-origin` | in-bounds candidate | freeze static roots, index rules, validators, range behavior, compression interaction, traversal/symlink policy | makes origin delivery auditable as a first-class profile | profile spec, operator page, cert bundle | traversal denial, HEAD/GET parity, Range/If-Range correctness | implement first |
| `P2` | Default truth | Base default audit | in-bounds candidate | audit zero-config defaults after normalization across all public flags and internal runtime defaults | defaults must stop being split across model/constants/CLI/normalize | `DEFAULT_AUDIT.json`, `DEFAULT_AUDIT.md` | post-normalization parity, three-state default tests | immediately after `P1` |
| `P2` | Default truth | Profile-effective default audit | in-bounds candidate | audit effective defaults after profile overlay for every blessed profile | profile docs cannot drift from runtime | `PROFILE_DEFAULTS/*.json`, `PROFILE_DEFAULTS/*.md`, inheritance manifest | overlay parity, unsafe-default denial, profile doc/runtime sync | immediately after `P1` |
| `P2` | Default truth | Reviewed flag contract registry | in-bounds candidate | every public flag/default row gets reviewed status, linked risks, claims, and tests | makes CLI/help/docs/runtime one truth surface | reviewed `flag_contracts.json` | flag review coverage, doc/runtime/help sync tests | immediately after `P1` |
| `P3` | Public policy closure | Proxy trust model | in-bounds candidate | freeze canonical trust sources, hop/listener trust, fail-closed behavior | request identity must stop being ambiguous | normative proxy contract | spoofed chain rejection, mixed-trust rejection | wave 2 |
| `P3` | Public policy closure | Proxy precedence plus normalization | in-bounds candidate | freeze precedence for `Forwarded` and `X-Forwarded-*`, host/proto/port conflicts, normalized outputs | prevents redirect and host reconstruction drift | precedence tables, normalization contract | duplicate/conflicting host/proto/port tests, root-path injection tests | wave 2 |
| `P3` | Public policy closure | CONNECT relay policy | in-bounds candidate | make CONNECT allow/deny, target normalization, anti-abuse posture explicit | one of the highest-risk hidden surfaces | policy docs, attack corpus slice | open-proxy denial, loopback/private-IP denial, DNS rebinding tests | wave 2 |
| `P3` | Public policy closure | Trailer policy | in-bounds candidate | freeze trailer acceptance/emission across H1/H2/H3 | stops transport-specific drift | policy docs, flag metadata | trailer correctness and malformed-trailer negatives | wave 2 |
| `P3` | Public policy closure | Content-coding policy | in-bounds candidate | freeze compression/content-coding negotiation behavior | must align static/origin/proxy behavior | policy docs, origin hooks | coding negotiation tests, compressed-range tests | wave 2 |
| `P3` | Public policy closure | ALPN/revocation/H2C/WS compression/limits/drain | in-bounds candidate | promote internal or partial controls into certified public controls | carries forward missing public surfaces from prior support matrices | CLI/help/docs, policy metadata, operator pages | ALPN tests, OCSP/CRL tests, H2C tests, WS compression tests, idle/limit/drain tests | wave 2 |
| `P4` | QUIC semantic closure | Early-data admission policy | in-bounds candidate | freeze deny-all, safe-only, allowlist, and app-mark 0-RTT policy | largest remaining QUIC semantic gap | early-data contract | admission matrix, unsafe-method rejection | wave 3 |
| `P4` | QUIC semantic closure | Replay policy | in-bounds candidate | freeze immediate forward vs buffer vs downgrade vs `425` | replay behavior must be explicit | replay policy spec | replay tests, `425` retry tests, intermediary propagation tests | wave 3 |
| `P4` | QUIC semantic closure | Multi-instance early-data policy | in-bounds candidate | define anti-replay coordination and load-balancer-specific behavior | prevents single-node-only claims | topology policy, deployment notes | multi-node replay, shared-ticket edge cases | wave 3 |
| `P4` | QUIC semantic closure | Retry plus app-visible semantics | in-bounds candidate | freeze Retry/0-RTT interaction and what ASGI apps can observe | runtime semantics must be honest | Retry/0-RTT interaction spec, runtime contract | invalid Retry, duplicate Retry, app-visibility consistency tests | wave 3 |
| `P4` | QUIC semantic closure | Independent QUIC state claims | in-bounds candidate | separate claims for Retry, resumption, 0-RTT, migration, and GOAWAY/QPACK pressure | avoids vague H3 supported language | profile bindings, operator docs | token integrity, migration spoofing, GOAWAY/QPACK stress | wave 3 |
| `P5` | Origin delivery contract | Path resolution | in-bounds candidate | freeze percent-decoding order, dot-segment normalization, separator/symlink/mount-root rules | static/pathsend semantics must be auditable | normative origin contract | traversal, encoded traversal, symlink escape tests | wave 4 |
| `P5` | Origin delivery contract | File selection plus HTTP semantics | in-bounds candidate | freeze index/slash/MIME behavior, validators, range, `206`/`304`/`416`, compression interaction | prevents platform-specific origin drift | origin contract, conformance corpus | HEAD parity, conditional conflicts, range-past-EOF tests | wave 4 |
| `P5` | Origin delivery contract | ASGI `pathsend` contract | in-bounds candidate | freeze stat timing, zero-copy expectations, mid-send mutation/error mapping, disconnect behavior | pathsend is package-owned and must be explicit | origin contract, operator docs | file-replaced-mid-send, partial-send, disconnect-race tests | wave 4 |
| `P6` | Observability | QUIC/H3 counter families | in-bounds candidate | freeze transport, security, loss, and H3 counters as a stable operator surface | diagnosability comes after semantic closure | metrics schema, operator docs | counter correctness under retry/migration/loss | wave 5 |
| `P6` | Observability | Export surfaces | in-bounds candidate | add StatsD/DogStatsD and OpenTelemetry export as explicit supported surfaces | exposes metrics/tracing beyond local plumbing | export config/docs | export smoke, schema compatibility checks | wave 5 |
| `P6` | Observability | qlog experimental stance | in-bounds candidate | keep qlog export explicit, unstable, versioned, and redacted | useful, but must not be overclaimed | experimental export spec, schema marker/versioning | redaction, schema-version, trace-integrity tests | wave 5 |
| `P7` | Negative certification | Fail-state registry | in-bounds candidate | freeze expected reject/close/abort/log/metric behavior per risky surface | safe failure must become claimable | negative-cert registry | assertion coverage tests | wave 6 |
| `P7` | Negative certification | Proxy/early-data/QUIC corpora | in-bounds candidate | preserve adversarial suites for spoofing, replay, Retry, migration, malformed tokens, amplification pressure | proves security behavior, not just happy paths | attack corpora, expected outcomes | negative suites with preserved evidence | wave 6 |
| `P7` | Negative certification | Origin/CONNECT/TLS/topology corpora | in-bounds candidate | preserve traversal, relay abuse, X.509 failure, and mixed-topology negative suites | closes the works-locally-only gap | corpora, expected outcomes, evidence bundles | traversal, open relay, wrong EKU/SAN, mixed-topology tests | wave 6 |
| `P8` | Governance plus promotion discipline | Risk register plus traceability | in-bounds candidate | make risk objects machine-readable and linked to claims/tests/evidence | governance must become auditable, not prose | `RISK_REGISTER*`, `RISK_TRACEABILITY.json`, schema/docs | schema, ID uniqueness, referential integrity, blocking-risk tests | parallel with `P2`-`P7`, required before promotion |
| `P8` | Governance plus promotion discipline | Pytest-only forward motion | in-bounds candidate | make `pytest` the sole forward runner and contain legacy `unittest` under inventory | stops test-style drift | `TEST_STYLE_POLICY.md`, `LEGACY_UNITTEST_INVENTORY.json` | no new unittest imports/classes, mirror-exists tests | parallel with `P2`-`P7` |
| `P8` | Governance plus promotion discipline | Release-gated evidence plus interop plus perf | in-bounds candidate | preserve evidence bundles, interop bundles, and performance artifacts as release inputs | claims must be replayable and durable | boundary manifests, interop bundles, perf bundles | release-gate suite, artifact retention checks | before any strong promotion language |
| `P8` | Spec hygiene | RFC 9651 structured-fields baseline | in-bounds candidate | move structured-fields behavior and claims to RFC 9651 rather than RFC 8941 | standards baseline already changed | SFV conformance tests, dependency review, claim sync | round-trip/canonical serialization tests, stale-reference lint | parallel, but must finish before promotion |
