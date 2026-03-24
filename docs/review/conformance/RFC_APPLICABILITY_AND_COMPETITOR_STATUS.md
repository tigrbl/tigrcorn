# RFC applicability and competitor status

This document answers three concrete questions for the current `tigrcorn` checkpoint:

1. Which RFCs from the user-supplied HTTP integrity / caching / signatures table are actually applicable to `tigrcorn`?
2. Which additional RFC-rooted features should `tigrcorn` conform to next?
3. What do comparable ASGI servers currently document as supported surfaces?

## Executive result

For the RFC table in question, the honest classification is:

- **Core and currently applicable to `tigrcorn`**
  - RFC 9112
  - RFC 9113
  - RFC 9114
  - RFC 9110, but only the already-bounded sections `§9.3.6` CONNECT, `§6.5` trailer fields, and `§8` content coding
- **Good next RFCs to add if the goal is stronger origin-server HTTP semantics**
  - RFC 7232
  - RFC 9530
- **Only conditionally applicable if the product boundary expands beyond a transport/server core**
  - RFC 9111
  - RFC 9421
- **Not currently appropriate as core transport-server RFC targets**
  - RFC 7515
  - RFC 7516
  - RFC 7519
  - RFC 8152
  - RFC 9052

That means `tigrcorn` should **first finish stronger evidence for the RFCs it already claims**, and **then add RFC 7232 and RFC 9530 before considering RFC 9111 or RFC 9421**.

## Applicability model used here

This review uses four buckets:

1. **Core current boundary** — already inside the package's declared transport/server certification boundary.
2. **Adjacent next** — not yet implemented, but directly adjacent to what an origin server can reasonably own.
3. **Conditional expansion** — useful only if the product expands into cache, gateway, or signed-message roles.
4. **Non-core product layer** — better treated as a different product boundary (identity, JOSE, COSE, application security envelope work).

## RFC-by-RFC applicability

| RFC | Applicability to current `tigrcorn` | Current checkpoint status | Recommendation |
|---|---|---|---|
| RFC 9112 | **Core current boundary** | Targeted and supported | Retain and keep release-gated |
| RFC 9113 | **Core current boundary** | Targeted and supported | Retain and keep release-gated |
| RFC 9114 | **Core current boundary** | Targeted and supported | Retain and keep release-gated |
| RFC 9110 | **Core current boundary, partial only** | Targeted only for CONNECT, trailers, and content coding | Finish stricter evidence for existing sections before broadening scope |
| RFC 7232 | **Adjacent next** | Not currently supported | Next high-value HTTP semantics target |
| RFC 9530 | **Adjacent next** | Not currently supported | Add after representation metadata / validator work exists |
| RFC 9111 | **Conditional expansion** | Not currently supported | Defer unless `tigrcorn` becomes a cache, revalidation, or static-asset product |
| RFC 9421 | **Conditional expansion** | Not currently supported | Defer unless `tigrcorn` becomes an edge/gateway signing product |
| RFC 7515 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 7516 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 7519 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 8152 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |
| RFC 9052 | **Non-core product layer** | Not currently supported | Keep outside transport-server boundary |

## What `tigrcorn` should conform to next

### 1. Finish the stricter evidence story for RFCs already inside the boundary

Before adding new breadth, the repository should close the stricter all-surfaces-independent gaps already documented for:

- RFC 7692
- RFC 9110 `§9.3.6`
- RFC 9110 `§6.5`
- RFC 9110 `§8`
- RFC 6960

Reason: these are already package-owned surfaces. The honest next move is stronger preserved third-party evidence, public operator/runtime closure, and performance closure — not new unaudited RFC breadth.

### 2. Add RFC 7232 as the next HTTP semantic feature family

If `tigrcorn` wants to move beyond pure transport/server framing into stronger origin behavior, RFC 7232 is the highest-value next target.

Recommended scope:

- strong and weak ETag generation for package-generated or buffered responses
- `If-None-Match` evaluation
- `304 Not Modified` decision engine
- clear rules for static-file, buffered, and streaming response classes
- first-class tests and machine-readable certification manifests

This should be implemented as an explicit representation-metadata subsystem rather than scattered header handling.

### 3. Add RFC 9530 immediately after RFC 7232

Once response metadata exists, RFC 9530 becomes a natural follow-on.

Recommended scope:

- `Content-Digest` for buffered payloads first
- `Repr-Digest` once representation metadata is stable
- optional trailer-mode digest emission later, only when streaming semantics are clearly bounded
- verifier hooks for operator-controlled integrity validation where appropriate

### 4. Treat RFC 9111 as optional product expansion, not automatic server scope

RFC 9111 is only a good target if `tigrcorn` explicitly wants to own cache keys, revalidation policy, freshness handling, and potentially static-asset/reverse-proxy behavior.

If the package remains a transport-centric ASGI server, RFC 9111 should stay **deferred**.

### 5. Treat RFC 9421 as optional gateway / edge work

RFC 9421 is compelling only if the package wants to act as a signed-message edge, gateway, or verification point.

If the package remains focused on serving ASGI applications over HTTP/1.1, HTTP/2, HTTP/3, TLS, and QUIC, RFC 9421 should stay **deferred**.

### 6. Keep JOSE / COSE out of the transport boundary unless the product expands

RFC 7515 / RFC 7516 / RFC 7519 / RFC 8152 / RFC 9052 are not natural core transport-server obligations for `tigrcorn`.

They belong in a different product boundary such as:

- auth / identity platform
- token issuance / validation
- signed application payload envelopes
- secure message object models

## Competitor status — documented current support

### Evidence policy

The matrix below records what the reviewed official docs / READMEs explicitly present as first-class supported surfaces as of **2026-03-20**.

Important interpretation rule:

- **`no official support claim found`** does **not** prove impossibility
- it only means the reviewed official current source does not present that feature as a first-class documented product surface

### Condensed matrix

| Surface | tigrcorn | Uvicorn | Hypercorn | Daphne | Granian |
|---|---|---|---|---|---|
| HTTP/1.1 | Yes | Documented yes | Documented yes | Documented yes | Documented yes |
| HTTP/2 | Yes | No official support claim found | Documented yes | Documented yes | Documented yes |
| HTTP/3 / QUIC | Yes | No official support claim found | Documented optional yes | No official support claim found | Not current; repo says “eventually 3” |
| WebSockets | Yes | Documented yes | Documented yes | Documented yes | Documented yes |
| WebSocket permessage-deflate policy | Yes | Documented yes | No first-class current policy knob documented | No first-class current support documented | No first-class current support documented |
| TLS termination | Yes | Documented yes | Documented yes | Documented yes | Documented yes |
| mTLS / peer certificate controls | Yes | Documented yes | Documented yes | Not first-class documented | Documented yes |
| Public CONNECT / trailer / content-coding policy surfaces | Yes | No official support claim found | No official support claim found | No official support claim found | No official support claim found |
| RFC 7232 / RFC 9530 / RFC 9421 first-class subsystems | No | No official support claim found | No official support claim found | No official support claim found | No official support claim found |

## Competitor notes

### Uvicorn

Current official docs present Uvicorn as an ASGI server that **currently supports HTTP/1.1 and WebSockets**. Its current documented HTTP implementation choices are `h11` and `httptools`, and it has a first-class `--ws-per-message-deflate` setting. Its HTTPS settings include `--ssl-cert-reqs` and `--ssl-ca-certs`, which gives it a documented client-certificate / mTLS-style SSL control surface. It does **not** currently present HTTP/2 or HTTP/3 as first-class supported surfaces in the reviewed docs.

### Hypercorn

Current official docs present Hypercorn as supporting **HTTP/1, HTTP/2, and WebSockets over HTTP/1 and HTTP/2**. Its current README also says it can **optionally** serve HTTP/3 using `aioquic` and `--quic-bind`. The configuration guide exposes ALPN protocol defaults, `--quic-bind`, `--verify-mode`, `--ca-certs`, and `--websocket-ping-interval`.

This makes Hypercorn the closest currently documented peer to `tigrcorn` on the protocol matrix, although the current official docs still do not present RFC 7232 / RFC 9530 / RFC 9421 as first-class product subsystems.

### Daphne

Current official docs present Daphne as an **HTTP, HTTP2, and WebSocket** ASGI server. Its README says HTTP/2 support is native but requires Twisted `http2` and `tls` extras plus TLS. The same README says Daphne only supports “normal” HTTP/2 requests and does not yet support extended HTTP/2 features like server push.

For WebSocket extensions, the current reviewed repository state still shows an open pull request titled **“Allow to accept websocket extensions”**, so the honest public-status label here is **not first-class documented** rather than a clean “yes”.

### Granian

Granian’s current official README presents it as supporting **HTTP/1 and HTTP/2**, **HTTPS and mTLS**, and **WebSockets**. Its options list shows `--http [auto|1|2]`, `--ws / --no-ws`, `--backlog`, and `--backpressure`. The same README says the design goal is support for versions 1, 2, and **eventually 3**, which means HTTP/3 is not yet a current first-class documented surface there.

Granian is therefore strong on performance/operator features, but not a currently documented HTTP/3 / QUIC peer in the same way `tigrcorn` is.

## Bottom line

If the question is **“which RFCs from the user table are truly applicable right now?”**, the answer is:

- **current core**: RFC 9112, RFC 9113, RFC 9114, and bounded RFC 9110 sections
- **best next additions**: RFC 7232, then RFC 9530
- **defer unless product expands**: RFC 9111 and RFC 9421
- **keep outside core**: JOSE / COSE RFCs

If the question is **“how should `tigrcorn` prioritize its next standards work?”**, the answer is:

1. finish stricter evidence and surface closure for already-claimed RFCs
2. implement RFC 7232
3. implement RFC 9530
4. only then reconsider RFC 9111 / RFC 9421
