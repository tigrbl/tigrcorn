# Phase 9D3 content-coding independent closure

This checkpoint executes **Phase 9D3** of `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`.

It closes the strict-target closure for **RFC 9110 §8** by preserving passing independent third-party content-coding artifacts across HTTP/1.1, HTTP/2, and HTTP/3 in the 0.3.9 working release root.

## What changed in this checkpoint

1. The deterministic content-coding fixture app remains the proof target at `tests/fixtures_pkg/interop_content_coding_app.py`.
2. The third-party wrappers preserve explicit content-coding modes for curl, h2, and aioquic.
3. The 0.3.9 working independent bundle now contains preserved **passing** content-coding artifacts for all three carriers.
4. The local content-coding behavior bundle continues to preserve gzip parity plus identity-only and strict negative vectors.

## Current preserved third-party artifact status

- HTTP/1.1 / `http11-content-coding-curl-client` — **passed**
- HTTP/2 / `http2-content-coding-curl-client` — **passed**
- HTTP/3 / `http3-content-coding-aioquic-client` — **passed**

The HTTP/3 artifact now records:

- peer exit code: `0`
- negotiated protocol: `h3`
- response status: `200`
- `Content-Encoding`: `gzip`
- decoded body: `compress-me`
- `Vary`: `accept-encoding`

## Runtime and validation surfaces covered here

- `Accept-Encoding` negotiation on HTTP/1.1, HTTP/2, and HTTP/3
- `Content-Encoding` selection and encoded payload delivery
- `Vary: accept-encoding` emission on the encoded path
- identity-only and strict failure semantics preserved in the local behavior bundle
- parity between HTTP/1.1, HTTP/2, and HTTP/3 on the RFC-scoped path

Primary runtime areas for this work are:

- `src/tigrcorn/protocols/content_coding.py`
- `src/tigrcorn/asgi/send.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `src/tigrcorn/protocols/http3/handler.py`

## Honest current result

This checkpoint makes **RFC 9110 §8** green at the required `independent_certification` tier under the strict target.

What is true now:

- the authoritative boundary remains green
- the strict target is green
- the composite promotion target is green
- there are no remaining non-passing strict-target independent scenarios in the 0.3.9 working release root
