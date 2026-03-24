# RFC applicability and competitor support status

This document answers three current-state questions for this checkpoint:

1. Which RFCs from the user-shared HTTP table are actually applicable to the current `tigrcorn` product boundary?
2. Which additional RFC-rooted features should `tigrcorn` conform to next?
3. What do the public docs for Uvicorn, Hypercorn, Daphne, and Granian currently show as supported?

## Executive result

For the current checkpoint, the applicable RFCs from the user-shared table split into four groups:

- **Core / currently applicable to `tigrcorn` as a transport server**
  - RFC 9112
  - RFC 9113
  - RFC 9114
  - bounded parts of RFC 9110: CONNECT, trailer fields, and content coding
- **Adjacent and reasonable next expansions if `tigrcorn` wants broader origin-server HTTP semantics**
  - RFC 7232
  - RFC 9530
- **Conditionally applicable only if the product boundary expands into cache or signed-message roles**
  - RFC 9111
  - RFC 9421
- **Not naturally part of the current transport boundary unless the product expands into auth / token / attestation surfaces**
  - RFC 7515
  - RFC 7516
  - RFC 7519
  - RFC 8152
  - RFC 9052

The honest current answer is therefore:

- `tigrcorn` should continue to treat **RFC 9112 / RFC 9113 / RFC 9114** as core.
- `tigrcorn` should treat **RFC 9110** as an intentionally bounded target until the package is ready to claim substantially more HTTP semantics than CONNECT, trailers, and content coding.
- `tigrcorn` should treat **RFC 7232 / RFC 9530** as the best next HTTP-semantic expansion targets after the current strict backlog closes.
- `tigrcorn` should treat **RFC 9111 / RFC 9421** as conditional expansion targets, not automatic transport-server obligations.
- `tigrcorn` should **not** treat JOSE or COSE RFCs as mandatory transport-server targets unless a separate product boundary is created for token, signature-envelope, or attestation features.

## Applicability classification for the user-shared RFC table

| RFC | Applicability to current `tigrcorn` | Current checkpoint state | Recommended posture |
|---|---|---|---|
| RFC 9112 | **Core** | Targeted and independently certified | Keep as a core transport target |
| RFC 9113 | **Core** | Targeted and independently certified | Keep as a core transport target |
| RFC 9114 | **Core** | Targeted and independently certified | Keep as a core transport target |
| RFC 9110 | **Core but bounded** | Targeted only for CONNECT, trailer fields, and content coding | Keep bounded unless the certification boundary is deliberately widened |
| RFC 7232 | **Adjacent expansion** | Not currently targeted; only header-name / generic-status adjacency exists | Add only if `tigrcorn` wants full origin-side validator and conditional-request semantics |
| RFC 9111 | **Conditional expansion** | Not currently targeted | Add only if `tigrcorn` wants cache/revalidation correctness beyond today’s bounded content-coding path |
| RFC 9530 | **Adjacent expansion** | Not currently targeted | Add if content / representation digests become a product requirement |
| RFC 9421 | **Conditional expansion** | Not currently targeted | Add if signed HTTP requests/responses become a first-class deployment goal |
| RFC 7515 | **Separate auth / crypto boundary** | Not currently targeted | Keep optional unless JOSE becomes a declared package surface |
| RFC 7516 | **Separate auth / crypto boundary** | Not currently targeted | Keep optional unless encrypted JOSE payloads become a declared package surface |
| RFC 7519 | **Separate auth / crypto boundary** | Not currently targeted | Keep optional unless JWT issuance / validation becomes a declared package surface |
| RFC 8152 | **Separate binary envelope / attestation boundary** | Not currently targeted | Keep optional unless COSE becomes a declared package surface |
| RFC 9052 | **Separate binary envelope / attestation boundary** | Not currently targeted | Keep optional unless COSE bis becomes a declared package surface |

## What `tigrcorn` should conform to next

There are two different “next” layers here.

### Layer A — finish the package’s own stricter target first

The current package already says the following work remains before the stronger all-surfaces-independent profile can be claimed:

- promote RFC 7692 (`permessage-deflate`) from local conformance to independent certification with preserved third-party artifacts
- promote RFC 9110 CONNECT from local conformance to independent certification with preserved third-party artifacts
- promote RFC 9110 trailers from local conformance to independent certification with preserved third-party artifacts
- promote RFC 9110 content coding from local conformance to independent certification with preserved third-party artifacts
- promote RFC 6960 OCSP policy validation from local conformance to independent certification with preserved third-party artifacts
- finish the stronger QUIC / HTTP/3 flow-control overlay with preserved third-party evidence
- complete the missing public operator surface and performance program

That means the **first** conformance priority should still be to finish the package’s own strict target honestly before widening the certification boundary.

### Layer B — if the package adopts more of the user-shared RFC table

If the package decides to grow into broader HTTP metadata / integrity semantics, the most sensible order is:

1. **RFC 7232 conditional requests**
   - entity-tag generation
   - strong / weak validator handling
   - `If-None-Match` evaluation
   - `304 Not Modified` decisioning
   - precondition failure handling where applicable
2. **RFC 9530 digests**
   - `Content-Digest`
   - `Repr-Digest`
   - verification hooks for inbound or forwarded integrity assertions
3. **RFC 9111 origin-side caching / revalidation correctness**
   - explicit cacheability and revalidation behavior
   - `Vary` normalization beyond the current content-coding path
   - policy-tested interaction between validators and cache metadata
   - only if `tigrcorn` deliberately adopts cache-aware origin or intermediary responsibilities
4. **RFC 9421 HTTP Message Signatures**
   - covered-component selection
   - signature generation
   - verification and policy controls
   - only if `tigrcorn` deliberately adopts signed edge / gateway responsibilities
5. **RFC 8941 Structured Field Values** (additional dependency not in the user-shared table)
   - this is the practical prerequisite for clean RFC 9530 and RFC 9421 work

### RFCs that should remain optional unless the product boundary changes

The following are reasonable technologies, but they do **not** naturally belong in the current `tigrcorn` transport-server certification boundary:

- RFC 7515 / RFC 7516 / RFC 7519 (JOSE)
- RFC 8152 / RFC 9052 (COSE)

They should only become conformance targets if `tigrcorn` explicitly takes on one or more of these roles:

- token issuer / validator
- signed control-plane object carrier
- signed attestation or binary envelope subsystem
- application-facing auth / identity platform rather than transport server only

## Public competitor support snapshot

This section is a **public-doc snapshot**, not a certification claim. “Not documented” means the reviewed official docs did not present that feature as a first-class server surface.

### RFC- and feature-shaped summary

| Surface | Tigrcorn | Uvicorn | Hypercorn | Daphne | Granian |
|---|---|---|---|---|---|
| RFC 9112 HTTP/1.1 server | Y | Y | Y | Y | Y |
| RFC 9113 HTTP/2 server | Y | N | Y | Y | Y |
| RFC 9114 HTTP/3 server | Y | N | P | N | N |
| RFC 9110 bounded CONNECT / trailers / content coding as a package-owned target | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 7232 conditional requests as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| RFC 9111 caching as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| RFC 9530 digests as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| RFC 9421 HTTP Message Signatures as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| JOSE / COSE as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |

### Operational positioning from reviewed public docs

| Server | Publicly documented protocol scope | Publicly documented operator strengths | Honest gap vs. `tigrcorn` |
|---|---|---|---|
| `tigrcorn` | HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, TLS/mTLS, ALPN, X.509, bounded CONNECT / trailers / content coding | Deep RFC program and preserved evidence bundles; richer H3 / QUIC posture than the reviewed competitors | CLI/operator parity and published performance discipline still trail the best-established competitors |
| Uvicorn | HTTP/1.1 and WebSockets | Strong developer/operator CLI: app-dir, reload, reload include/exclude, workers, env-file, log-config, proxy/header controls, TLS options, backlog/concurrency, WebSocket limits and `per-message-deflate` | No current public HTTP/2 or HTTP/3 server claim in reviewed docs |
| Hypercorn | HTTP/1, HTTP/2, WebSockets over HTTP/1 and HTTP/2; optional HTTP/3 draft path via `aioquic` and `--quic-bind` | Strong config and runtime surface: TOML/Python/module config, ALPN, h2c, workers, worker class, pid, statsd, backlog, timeouts, root path, QUIC bind, WebSocket ping | Public positioning is broader than Uvicorn but still less explicit than `tigrcorn` on package-owned H3/QUIC certification |
| Daphne | HTTP, HTTP/2, and WebSocket | Straightforward listener surface: host/port, unix socket, fd passing, Twisted endpoint strings, TLS and HTTP/2 via Twisted extras | Narrower documented tuning and process-management surface; no public HTTP/3 story |
| Granian | HTTP/1 and HTTP/2, HTTPS and mTLS, WebSockets; public docs say HTTP/3 is a future direction rather than current support | Very strong runtime/performance knobs: workers, runtime mode, loop, task implementation, backlog, backpressure, HTTP/1 and HTTP/2 tuning, env vars, UDS permissions, reload and dotenv extras | No current public HTTP/3 support and no explicit RFC certification program in the reviewed docs |

## Practical recommendation

The pragmatic roadmap is:

1. **Do not expand the claimed boundary just because the user-shared RFC table exists.**
2. **Finish the package’s current strict target** (RFC 7692, RFC 9110 bounded sections at independent tier, RFC 6960, operator surface, performance gates).
3. **If broader HTTP metadata / integrity matters, add RFC 7232 and RFC 9530 next, then consider RFC 9111 and RFC 9421 only if the product boundary intentionally expands.**
4. **Keep JOSE and COSE out of the transport boundary** unless `tigrcorn` intentionally becomes more than a transport server.

## Honest bottom line

From the user-shared RFC table, the RFCs that are truly applicable to today’s `tigrcorn` are:

- RFC 9112
- RFC 9113
- RFC 9114
- bounded parts of RFC 9110

The RFCs that are reasonable **next expansions** are:

- RFC 7232
- RFC 9530

The RFCs that are reasonable **conditional expansions** are:

- RFC 9111
- RFC 9421

The RFCs that should remain **optional and boundary-dependent** are:

- RFC 7515
- RFC 7516
- RFC 7519
- RFC 8152
- RFC 9052
