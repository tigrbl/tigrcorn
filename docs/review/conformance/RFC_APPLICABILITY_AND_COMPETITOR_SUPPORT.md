> Scope note: this document is a focused current audit, not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for package-wide truth.

# RFC applicability and competitor support review

This note records the current boundary-aware answer for the RFC family discussed in the review.

## Executive result

- `tigrcorn` already treats **RFC 9112 / RFC 9113 / RFC 9114** as core transport targets.
- `tigrcorn` still treats **RFC 9110** as bounded to CONNECT, trailer fields, and content coding rather than claiming the entire RFC.
- `tigrcorn` now treats **RFC 7232 / RFC 7233** as package-owned direct entity semantics inside the current certification boundary.
- `tigrcorn` now also treats **RFC 8297** and the bounded **RFC 7838 §3** Alt-Svc header-field advertisement profile as package-owned direct-delivery semantics inside the current certification boundary.
- `tigrcorn` should treat **RFC 9218** as transport-adjacent optional work and keep it out until explicit prioritization semantics are intentionally adopted.
- `tigrcorn` should treat **RFC 9530** as the next optional adjacent HTTP-metadata expansion only if the product boundary intentionally grows further.
- `tigrcorn` should treat **RFC 9111 / RFC 9421** as conditional boundary-expansion work, not automatic transport-server obligations.
- `tigrcorn` should **not** treat JOSE or COSE RFCs as mandatory transport-server targets unless a separate product boundary is created for token, signature-envelope, or attestation features.

## Applicability classification for the RFC table

| RFC | Applicability to current `tigrcorn` | Current checkpoint state | Recommended posture |
|---|---|---|---|
| RFC 9112 | **Core** | Targeted and independently certified | Keep as a core transport target |
| RFC 9113 | **Core** | Targeted and independently certified | Keep as a core transport target |
| RFC 9114 | **Core** | Targeted and independently certified | Keep as a core transport target |
| RFC 9110 | **Core but bounded** | Targeted only for CONNECT, trailer fields, and content coding | Keep bounded unless the certification boundary is deliberately widened |
| RFC 7232 | **Core entity semantics** | Targeted and release-gated at local conformance | Keep as a core direct-server semantic target |
| RFC 7233 | **Core entity semantics** | Targeted and release-gated at local conformance | Keep as a core direct-server semantic target |
| RFC 8297 | **Core direct-delivery semantics** | Targeted and release-gated at local conformance | Keep as a core direct-server delivery target |
| RFC 7838 §3 | **Core direct-delivery semantics, bounded** | Targeted and release-gated at local conformance | Keep as the current bounded Alt-Svc header-field profile unless broader Alt-Svc framing is intentionally adopted |
| RFC 9218 | **Transport-adjacent optional** | Not currently targeted | Keep outside the current boundary until explicit prioritization semantics are adopted |
| RFC 9111 | **Conditional expansion** | Not currently targeted | Add only if `tigrcorn` wants cache/freshness correctness beyond today’s direct response semantics |
| RFC 9530 | **Adjacent expansion** | Not currently targeted | Add if content / representation digests become a product requirement |
| RFC 9421 | **Conditional expansion** | Not currently targeted | Add if signed HTTP requests/responses become a first-class deployment goal |
| RFC 7515 | **Separate auth / crypto boundary** | Not currently targeted | Keep optional unless JOSE becomes a declared package surface |
| RFC 7516 | **Separate auth / crypto boundary** | Not currently targeted | Keep optional unless encrypted JOSE payloads become a declared package surface |
| RFC 7519 | **Separate auth / crypto boundary** | Not currently targeted | Keep optional unless JWT issuance / validation becomes a declared package surface |
| RFC 8152 | **Separate binary envelope / attestation boundary** | Not currently targeted | Keep optional unless COSE becomes a declared package surface |
| RFC 9052 | **Separate binary envelope / attestation boundary** | Not currently targeted | Keep optional unless COSE bis becomes a declared package surface |

## What `tigrcorn` should conform to next

There are three different “next” layers here.

### Layer A — keep the current package boundary green and honest

The current package already claims the following direct entity and bounded-direct-delivery surfaces and should keep them aligned with tests, docs, and release-gate truth:

- RFC 7232
- RFC 7233
- RFC 8297
- RFC 7838 §3
- RFC 7692
- RFC 9110 CONNECT
- RFC 9110 trailers
- RFC 9110 content coding
- RFC 6960

### Layer B — transport-adjacent optional work

If the package decides to grow further inside the transport/runtime area without crossing into cache or integrity boundaries, the most sensible optional next item is:

1. **RFC 9218 prioritization**
   - only if `tigrcorn` deliberately adopts explicit prioritization semantics and evidence

### Layer C — if the package adopts more of the adjacent RFC family

If the package decides to grow further into broader HTTP metadata / integrity semantics, the most sensible next order is:

1. **RFC 9530 digests**
   - `Content-Digest`
   - `Repr-Digest`
2. **RFC 9111 origin-side caching / freshness correctness**
   - only if `tigrcorn` deliberately adopts cache-aware origin behavior
3. **RFC 9421 HTTP Message Signatures**
   - only if `tigrcorn` deliberately adopts signed edge / gateway responsibilities
4. **RFC 9651 Structured Fields** (supporting dependency, if digest/signature work is adopted)

### RFCs that should remain optional unless the product boundary changes

The following are reasonable technologies, but they do **not** naturally belong in the current `tigrcorn` direct-server certification boundary:

- RFC 7515 / RFC 7516 / RFC 7519 (JOSE)
- RFC 8152 / RFC 9052 (COSE)

## Public competitor support snapshot

This section is a **public-doc snapshot**, not a certification claim.

| Surface | Tigrcorn | Uvicorn | Hypercorn | Daphne | Granian |
|---|---|---|---|---|---|
| HTTP/1.1 | Y | Y | Y | Y | Y |
| HTTP/2 | Y | N | Y | Y | Y |
| HTTP/3 / QUIC | Y | N | P | N | N |
| Bounded RFC 9110 target | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 7232 conditional requests as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 7233 range requests as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 8297 Early Hints as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 7838 §3 Alt-Svc header-field advertisement as a first-class server feature | Y | Not documented | Not documented | Not documented | Not documented |
| RFC 9218 prioritization as a first-class server feature | N | Not documented | Not documented | Not documented | Not documented |
| RFC 9111 / RFC 9530 / RFC 9421 first-class server features | N | Not documented | Not documented | Not documented | Not documented |

## Honest bottom line

`tigrcorn` is currently strongest as a transport/runtime RFC implementation that now also owns direct response/entity semantics, direct-delivery Early Hints, and bounded Alt-Svc header-field advertisement.

It is **not** currently a prioritization product, cache-freshness product, digest-field product, HTTP-signature product, or JOSE/COSE platform.
