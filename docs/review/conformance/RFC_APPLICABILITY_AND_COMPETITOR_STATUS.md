> Scope note: this document is a focused current audit, not the canonical package-wide current-state source. Use `CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for package-wide truth.

# RFC applicability and competitor status

This document answers three concrete questions for the current `tigrcorn` checkpoint:

1. Which RFCs from the user-supplied HTTP semantics / entity / integrity table are actually applicable to `tigrcorn`?
2. Which additional RFC-rooted features should `tigrcorn` conform to next?
3. What do comparable ASGI servers currently document as supported surfaces?

## Executive result

For the RFC family in question, the honest classification is:

- **Core and currently applicable to `tigrcorn`**
  - RFC 9112
  - RFC 9113
  - RFC 9114
  - RFC 9110, but only the already-bounded sections `§9.3.6` CONNECT, `§6.5` trailer fields, and `§8` content coding
  - RFC 7232
  - RFC 7233
  - RFC 8297
  - RFC 7838, but only the bounded `§3` Alt-Svc header-field advertisement profile
- **Good next RFC to add only if the boundary intentionally grows further**
  - RFC 9530
- **Transport-adjacent but not currently targeted**
  - RFC 9218
- **Only conditionally applicable if the product boundary expands beyond a direct server/runtime**
  - RFC 9111
  - RFC 9421
- **Not currently appropriate as core transport-server RFC targets**
  - RFC 7515
  - RFC 7516
  - RFC 7519
  - RFC 8152
  - RFC 9052

That means `tigrcorn` should **retain RFC 7232, RFC 7233, RFC 8297, and the bounded RFC 7838 §3 profile as release-gated direct entity/direct-delivery semantics**, **keep RFC 9218 out until prioritization is a deliberate product goal**, and **only consider RFC 9530, RFC 9111, or RFC 9421 if the product boundary deliberately expands**.

## Applicability model used here

This review uses five buckets:

1. **Core current boundary** — already inside the package's declared direct-server certification boundary.
2. **Core current boundary, bounded** — part of the current boundary, but only through an explicitly limited section/profile.
3. **Adjacent next** — not yet implemented, but directly adjacent to what a direct server can reasonably own.
4. **Transport-adjacent optional** — protocol-adjacent work that is not inside the current boundary unless explicitly adopted.
5. **Conditional expansion** — useful only if the product expands into cache, gateway, or signed-message roles.
6. **Non-core product layer** — better treated as a different product boundary (identity, JOSE, COSE, application security envelope work).

## RFC-by-RFC applicability

| RFC | Applicability to current `tigrcorn` | Current checkpoint status | Recommendation |
|---|---|---|---|
| RFC 9112 | **Core current boundary** | Targeted and supported | Retain and keep release-gated |
| RFC 9113 | **Core current boundary** | Targeted and supported | Retain and keep release-gated |
| RFC 9114 | **Core current boundary** | Targeted and supported | Retain and keep release-gated |
| RFC 9110 | **Core current boundary, partial only** | Targeted only for CONNECT, trailers, and content coding | Keep bounded unless the certification boundary is deliberately widened |
| RFC 7232 | **Core current boundary** | Targeted and supported | Retain and keep release-gated as package-owned entity semantics |
| RFC 7233 | **Core current boundary** | Targeted and supported | Retain and keep release-gated as package-owned entity semantics |
| RFC 8297 | **Core current boundary** | Targeted and supported | Retain and keep release-gated as package-owned direct-delivery semantics |
| RFC 7838 | **Core current boundary, bounded profile** | Targeted and supported only for `§3` Alt-Svc header-field advertisement | Retain the bounded profile unless protocol-level Alt-Svc framing is deliberately adopted |
| RFC 9218 | **Transport-adjacent optional** | Not currently supported | Keep outside the boundary until prioritization semantics are a deliberate package goal |
| RFC 9530 | **Adjacent next** | Not currently supported | Add only if integrity fields become an intentional product requirement |
| RFC 9111 | **Conditional expansion** | Not currently supported | Defer unless `tigrcorn` becomes a cache/freshness product |
| RFC 9421 | **Conditional expansion** | Not currently supported | Defer unless `tigrcorn` becomes an edge/gateway signing product |
| RFC 7515 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 7516 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 7519 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 8152 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 9052 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |

## What `tigrcorn` should conform to next

### 1. Keep the current boundary evidence and current-state docs aligned

The newly formalized entity and direct-delivery semantics should remain release-gated and documentation-aligned for:

- RFC 7232
- RFC 7233
- RFC 8297
- RFC 7838 `§3`
- RFC 7692
- RFC 9110 `§9.3.6`
- RFC 9110 `§6.5`
- RFC 9110 `§8`
- RFC 6960

Reason: these are already inside the declared package boundary.

### 2. Keep RFC 9218 explicitly out until prioritization semantics are adopted

RFC 9218 is transport-adjacent work, but the current package boundary does not claim explicit prioritization semantics or operator surfaces. It should remain outside the current boundary until that becomes a deliberate package goal.

### 3. Add RFC 9530 only if integrity fields become an explicit product requirement

If `tigrcorn` wants to move beyond direct entity semantics into explicit integrity metadata, RFC 9530 is the next adjacent target.

That would require:

- `Content-Digest`
- `Repr-Digest`
- structured-field support where needed
- explicit certification policy and evidence for those fields

### 4. Keep RFC 9111 and RFC 9421 as conditional boundary expansions

These RFCs become relevant only if `tigrcorn` intentionally adopts one of these roles:

- cache-aware origin/static-asset behavior with freshness policy
- intermediary or gateway behavior
- signed HTTP request/response handling

### 5. Keep JOSE / COSE out of the direct-server boundary

RFC 7515 / RFC 7516 / RFC 7519 / RFC 8152 / RFC 9052 are not natural core transport-server obligations for `tigrcorn`.

## Public competitor support snapshot

This section is a **public-doc snapshot**, not a certification claim. “Not documented” means the reviewed official docs did not present that feature as a first-class server surface.

### RFC- and feature-shaped summary

| Surface | Tigrcorn | Uvicorn | Hypercorn | Daphne | Granian |
|---|---|---|---|---|---|
| RFC 9112 HTTP/1.1 server | Y | Y | Y | Y | Y |
| RFC 9113 HTTP/2 server | Y | N | Y | Y | Y |
| RFC 9114 HTTP/3 server | Y | N | P | N | N |
| RFC 9110 bounded CONNECT / trailers / content coding as a package-owned target | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 7232 conditional requests as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 7233 range requests as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 8297 Early Hints as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 7838 Alt-Svc header-field advertisement as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 9218 prioritization as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| RFC 9111 caching as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| RFC 9530 digests as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| RFC 9421 HTTP Message Signatures as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| JOSE / COSE as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |

### Operational positioning from reviewed public docs

| Server | Publicly documented protocol scope | Publicly documented operator strengths | Honest gap vs. `tigrcorn` |
|---|---|---|---|
| `tigrcorn` | HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, TLS/mTLS, ALPN, X.509, direct entity semantics for validators and byte ranges, bounded CONNECT / trailers / content coding, direct-delivery Early Hints, and bounded Alt-Svc header-field advertisement | Deep RFC program and preserved evidence bundles; richer H3 / QUIC posture than the reviewed competitors | CLI/operator parity and published performance discipline still trail the best-established competitors |
| Uvicorn | HTTP/1.1 and WebSockets | Strong developer/operator CLI: app-dir, reload, reload include/exclude, workers, env-file, log-config, proxy/header controls, TLS options, backlog/concurrency, WebSocket limits and `per-message-deflate` | No current public HTTP/2 or HTTP/3 server claim in reviewed docs |
| Hypercorn | HTTP/1, HTTP/2, WebSockets over HTTP/1 and HTTP/2; optional HTTP/3 draft path via `aioquic` and `--quic-bind` | Strong config and runtime surface: TOML/Python/module config, ALPN, h2c, workers, worker class, pid, statsd, backlog, timeouts, root path, QUIC bind, WebSocket ping | Public positioning is broader than Uvicorn but still less explicit than `tigrcorn` on package-owned H3/QUIC certification |
| Daphne | HTTP, HTTP/2, and WebSocket | Straightforward listener surface: host/port, unix socket, fd passing, Twisted endpoint strings, TLS and HTTP/2 via Twisted extras | Narrower documented tuning and process-management surface; no public HTTP/3 story |
| Granian | HTTP/1 and HTTP/2, HTTPS and mTLS, WebSockets; public docs say HTTP/3 is a future direction rather than current support | Very strong runtime/performance knobs: workers, runtime mode, loop, task implementation, backlog, backpressure, HTTP/1 and HTTP/2 tuning, env vars, UDS permissions, reload and dotenv extras | No current public HTTP/3 support and no explicit RFC certification program in the reviewed docs |

## Practical recommendation

The pragmatic roadmap is:

1. **Do not expand the claimed boundary just because a broader RFC table exists.**
2. **Keep the current package boundary green and aligned**, including RFC 7232, RFC 7233, RFC 8297, and the bounded RFC 7838 §3 surface.
3. **Keep RFC 9218 out unless explicit prioritization semantics become a deliberate package goal.**
4. **If broader HTTP metadata / integrity matters, add RFC 9530 next.**
5. **Consider RFC 9111 and RFC 9421 only if the product boundary intentionally expands.**
6. **Keep JOSE and COSE out of the transport boundary** unless `tigrcorn` intentionally becomes more than a transport/runtime server.

## Honest bottom line

From the RFC family in question, the RFCs that are truly applicable to today’s `tigrcorn` are:

- RFC 9112
- RFC 9113
- RFC 9114
- bounded parts of RFC 9110
- RFC 7232
- RFC 7233
- RFC 8297
- bounded RFC 7838 §3

The RFC that is a reasonable **next adjacent optional expansion** is:

- RFC 9530

The RFC that is a reasonable **transport-adjacent but still non-targeted** surface is:

- RFC 9218

The RFCs that are reasonable **conditional expansions** are:

- RFC 9111
- RFC 9421

The RFCs that should remain **optional and boundary-dependent** are:

- RFC 7515
- RFC 7516
- RFC 7519
- RFC 8152
- RFC 9052
