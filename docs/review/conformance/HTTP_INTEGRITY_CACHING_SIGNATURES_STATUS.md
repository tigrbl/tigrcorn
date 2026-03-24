# HTTP integrity, caching, and signatures status

This document answers a focused audit question for the current checkpoint:

> Are the HTTP integrity, caching, and signature RFCs listed below currently supported in `tigrcorn`? Are they targeted? Are they not targeted?

## Executive result

`tigrcorn` is currently **certifiably fully RFC compliant only under its declared authoritative certification boundary**.

That authoritative boundary is transport/server centric. It includes HTTP/1.1, HTTP/2, HTTP/3, QUIC, HPACK/QPACK, WebSocket, TLS 1.3, X.509 path validation, ALPN, OCSP policy, and only three bounded RFC 9110 areas:

- CONNECT semantics
- trailer fields
- content coding

It does **not** currently target the broader HTTP integrity / caching / signature stack made up of RFC 7232, RFC 9111, RFC 9530, RFC 9421, JOSE, or COSE.

That means the honest answer is:

- the package **does support part of the requested feature set** through RFC 9110 content-coding behavior
- the package **does not currently target most of the requested RFCs**
- the package **is not currently a full implementation of the requested HTTP integrity / caching / signatures stack**

## Current RFC status

| RFC | Title | Current status in this checkpoint | Targeted by current certification boundary? | Notes |
|---|---|---|---:|---|
| RFC 7232 | HTTP Conditional Requests | **Not supported** | No | No conditional-request engine was found for ETag, `If-None-Match`, or validator-driven `304` decisions. |
| RFC 9110 | HTTP Semantics | **Partially supported** | Yes, but only specific sections | Only RFC 9110 `§9.3.6` CONNECT, `§6.5` trailer fields, and `§8` content coding are in scope here. Full RFC 9110 is not claimed. |
| RFC 9111 | HTTP Caching | **Not supported** | No | No cache / revalidation subsystem was found. |
| RFC 9530 | Content-Digest / Repr-Digest | **Not supported** | No | No digest field generator or verifier was found. |
| RFC 7515 | JWS | **Not supported** | No | No JOSE signing surface is declared by the transport boundary. |
| RFC 7516 | JWE | **Not supported** | No | No JOSE encryption surface is declared by the transport boundary. |
| RFC 7519 | JWT | **Not supported** | No | No JWT token model or validation surface is declared by the transport boundary. |
| RFC 8152 | COSE | **Not supported** | No | No COSE envelope/signing surface was found. |
| RFC 9052 | COSE bis | **Not supported** | No | No COSE bis update surface was found. |
| RFC 9421 | HTTP Message Signatures | **Not supported** | No | No `Signature-Input` / `Signature` subsystem was found. |

## Current feature status

| Feature | Current status in this checkpoint | Targeted? | Closest existing implementation |
|---|---|---:|---|
| ETag | **Header-name only** | No | Present in HPACK/QPACK static header tables, but no ETag generation or comparison engine was found. |
| `If-None-Match` | **Header-name only** | No | Present in HPACK/QPACK static header tables, but no conditional evaluation path was found. |
| `304 Not Modified` | **Generic status support only** | No | HTTP serialization knows the status code and suppresses the body, but no RFC 7232 decision engine was found. |
| `Vary` | **Supported for content coding** | Yes | `Vary: accept-encoding` is emitted on the content-coding path. |
| `Accept-Encoding` | **Supported** | Yes | Request parsing and qvalue selection are implemented. |
| `Content-Encoding` | **Supported** | Yes | `gzip`, `deflate`, and optional `br` can be emitted. |
| `Content-Digest` | **Not supported** | No | No field implementation was found. |
| `Repr-Digest` | **Not supported** | No | No field implementation was found. |
| JOSE signing | **Not supported** | No | No JWS/JWE/JWT subsystem was found. |
| COSE signing | **Not supported** | No | No COSE subsystem was found. |
| HTTP signatures | **Not supported** | No | No RFC 9421 signing subsystem was found. |

## Closest existing modules

The current checkpoint does contain code that is adjacent to the requested space:

- `src/tigrcorn/protocols/content_coding.py`
  - parses `Accept-Encoding`
  - chooses a coding by qvalue
  - emits `Content-Encoding`
  - adds `Vary: accept-encoding`
- `src/tigrcorn/protocols/http1/serializer.py`
  - knows about status `304`
  - suppresses bodies for status classes that must not carry a body
- `src/tigrcorn/protocols/http2/hpack.py`
- `src/tigrcorn/protocols/http3/qpack.py`
  - include header-table entries for names such as `etag` and `if-none-match`

Those modules are **not** a full RFC 7232 / RFC 9111 / RFC 9530 / RFC 9421 / JOSE / COSE implementation.

## What is missing today

The current checkpoint does **not** contain a dedicated runtime subsystem for:

- conditional requests and representation validator comparison
- HTTP caching and revalidation
- `Content-Digest` or `Repr-Digest`
- HTTP Message Signatures
- JOSE token/signing/encryption handling
- COSE envelopes or signatures

## Why this does not contradict the package RFC claim

The package can still be honestly described as **certifiably fully RFC compliant under its own authoritative boundary** because that boundary does not claim the broader integrity/caching/signatures stack.

In other words:

- **under the package boundary:** current RFC claim is green
- **under the broader RFC list in this audit:** current RFC claim would be incomplete

## What would need to change to support the requested stack

1. Add a representation metadata subsystem that can compute validators and evaluate conditional requests before response emission.
2. Add explicit RFC 7232 and RFC 9111 target manifests, tests, release gates, and evidence bundles.
3. Add RFC 9530 digest generation and verification for content and representation digests.
4. Add an RFC 9421 HTTP Message Signatures subsystem, including covered-component selection, signing, and verification.
5. If JOSE or COSE support is desired, add them as an explicit product boundary rather than implying them through the transport boundary.
6. Extend machine-readable certification manifests so the package does not overclaim support before the new subsystems are evidence-backed.
