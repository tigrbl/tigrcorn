> Scope note: this document is a focused current audit, not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for package-wide truth.

# HTTP integrity, caching, and signatures status

This document answers a focused audit question for the current checkpoint:

> Are the HTTP integrity, caching, and signature RFCs listed below currently supported in `tigrcorn`? Are they targeted? Are they not targeted?

## Executive result

`tigrcorn` remains **certifiably fully RFC compliant under its declared authoritative certification boundary**.

That direct-server boundary is still transport/server centric, but it now also includes the package-owned HTTP entity semantics for:

- RFC 7232 conditional requests
- RFC 7233 byte range requests
- RFC 9110 `§9.3.6` CONNECT semantics
- RFC 9110 `§6.5` trailer fields
- RFC 9110 `§8` content coding

It still does **not** target the broader cache / integrity / signature stack made up of RFC 9111, RFC 9530, RFC 9421, JOSE, or COSE.

That means the honest answer is:

- the package **does support and target RFC 7232 and RFC 7233** as direct response/entity semantics
- the package **does not currently target broader cache freshness, digest, signature, JOSE, or COSE subsystems**
- the package **is not a full implementation of the broader HTTP integrity / caching / signatures stack**

## Current RFC status

| RFC | Title | Current status in this checkpoint | Targeted by current certification boundary? | Notes |
|---|---|---|---:|---|
| RFC 7232 | HTTP Conditional Requests | **Supported and targeted** | Yes | ETag generation, validator comparison, `If-Match`, `If-None-Match`, `If-Modified-Since`, `If-Unmodified-Since`, and `304` / `412` decisioning are implemented and release-gated through local conformance. |
| RFC 7233 | HTTP Range Requests | **Supported and targeted** | Yes | Byte ranges, multipart byteranges, `If-Range`, `206`, `416`, `Content-Range`, and `Accept-Ranges` are implemented and release-gated through local conformance. |
| RFC 9110 | HTTP Semantics | **Partially supported** | Yes, but only specific sections | RFC 9110 remains bounded to `§9.3.6` CONNECT, `§6.5` trailer fields, and `§8` content coding. Full RFC 9110 is not claimed. |
| RFC 9111 | HTTP Caching | **Not supported** | No | No cache freshness / revalidation subsystem is claimed by the current direct-server boundary. |
| RFC 9530 | Digest Fields | **Not supported** | No | No `Content-Digest` / `Repr-Digest` field generator or verifier is claimed. |
| RFC 7515 | JWS | **Not supported** | No | No JOSE signing surface is declared by the direct-server boundary. |
| RFC 7516 | JWE | **Not supported** | No | No JOSE encryption surface is declared by the direct-server boundary. |
| RFC 7519 | JWT | **Not supported** | No | No JWT token model or validation surface is declared by the direct-server boundary. |
| RFC 8152 | COSE | **Not supported** | No | No COSE envelope/signing surface is claimed. |
| RFC 9052 | COSE bis | **Not supported** | No | No COSE bis update surface is claimed. |
| RFC 9421 | HTTP Message Signatures | **Not supported** | No | No `Signature-Input` / `Signature` subsystem is claimed. |

## Current feature status

| Feature | Current status in this checkpoint | Targeted? | Closest existing implementation |
|---|---|---:|---|
| ETag | **Supported** | Yes | `src/tigrcorn/http/etag.py`, `src/tigrcorn/http/entity.py` |
| `If-None-Match` | **Supported** | Yes | `src/tigrcorn/http/conditional.py` |
| `If-Match` | **Supported** | Yes | `src/tigrcorn/http/conditional.py` |
| `If-Modified-Since` / `If-Unmodified-Since` | **Supported** | Yes | `src/tigrcorn/http/conditional.py` |
| `304 Not Modified` | **Supported by conditional engine** | Yes | `src/tigrcorn/http/conditional.py`, `src/tigrcorn/http/entity.py` |
| Byte ranges / multipart byteranges | **Supported** | Yes | `src/tigrcorn/http/range.py`, `src/tigrcorn/http/entity.py`, `src/tigrcorn/static.py` |
| `If-Range` | **Supported** | Yes | `src/tigrcorn/http/range.py` |
| `Vary` | **Supported for content coding** | Yes | `src/tigrcorn/protocols/content_coding.py` |
| `Accept-Encoding` | **Supported** | Yes | `src/tigrcorn/protocols/content_coding.py` |
| `Content-Encoding` | **Supported** | Yes | `src/tigrcorn/protocols/content_coding.py` |
| `Content-Digest` | **Not supported** | No | No field implementation is currently claimed |
| `Repr-Digest` | **Not supported** | No | No field implementation is currently claimed |
| JOSE signing | **Not supported** | No | No JOSE subsystem is currently claimed |
| COSE signing | **Not supported** | No | No COSE subsystem is currently claimed |
| HTTP signatures | **Not supported** | No | No RFC 9421 subsystem is currently claimed |

## Closest existing modules

The current checkpoint contains package-owned code directly in the new boundary area:

- `src/tigrcorn/http/etag.py`
- `src/tigrcorn/http/conditional.py`
- `src/tigrcorn/http/range.py`
- `src/tigrcorn/http/entity.py`
- `src/tigrcorn/static.py`
- `src/tigrcorn/protocols/content_coding.py`

Those modules are **not** a full RFC 9111 / RFC 9530 / RFC 9421 / JOSE / COSE implementation.

## What is still missing today

The current checkpoint does **not** contain a dedicated runtime subsystem for:

- cache freshness / cache-control / revalidation policy
- `Content-Digest` or `Repr-Digest`
- HTTP Message Signatures
- JOSE token/signing/encryption handling
- COSE envelopes or signatures

## Why this does not contradict the package RFC claim

The package can still be honestly described as **certifiably fully RFC compliant under its own authoritative boundary** because that boundary now claims RFC 7232 and RFC 7233 directly, while still not claiming the broader cache / integrity / signatures stack.

In other words:

- **under the package boundary:** current RFC claim is green
- **under the broader cache / integrity / signatures stack:** current RFC claim remains intentionally incomplete

## What would need to change to support the broader requested stack

1. Add explicit RFC 9111 cache / freshness policy if `tigrcorn` deliberately adopts cache-aware behavior.
2. Add RFC 9530 digest generation and verification for content and representation digests if integrity fields become a product requirement.
3. Add an RFC 9421 HTTP Message Signatures subsystem only if signed edge / gateway behavior becomes a deliberate product goal.
4. If JOSE or COSE support is desired, add them as an explicit product boundary rather than implying them through the direct-server transport boundary.
5. Extend machine-readable certification manifests only after those broader subsystems are evidence-backed and intentionally claimed.
