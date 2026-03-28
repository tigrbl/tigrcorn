> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool references. It is not the canonical package-wide current-state source. Use `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json` for current package truth.

# Current Repository State — Phase 2 Core HTTP Entity Semantics Checkpoint

## Scope of this checkpoint

This checkpoint is a **Phase 2 delivery** focused on:

- direct-server HTTP entity semantics
- conditional requests and validators
- byte ranges and partial content
- cross-protocol body/header metadata closure for H1 / H2 / H3
- content-coding hardening at the direct server boundary

This checkpoint explicitly **does not** certify the repository as fully complete against the broader expansion program that includes cache/freshness policy, integrity/trust features, gateway/enforcement features, or all future Phase 3–4 work.

## Current certification statement

- **Current internal promotion target**: not re-certified globally in this checkpoint.
- **Certifiably fully featured against the expanded program**: **no**.
- **Certifiably fully RFC compliant against the expanded program**: **no**.

This checkpoint can truthfully claim that it closes a substantial amount of **Phase 2 direct-server entity behavior** and that the focused validation bundle listed below passed.

## Implemented in this checkpoint

### New HTTP entity modules

Added:

- `src/tigrcorn/http/etag.py`
- `src/tigrcorn/http/conditional.py`
- `src/tigrcorn/http/range.py`
- `src/tigrcorn/http/entity.py`
- `src/tigrcorn/http/__init__.py`

### Conditional request engine

Implemented:

- strong ETag generation for complete, known response bodies when the app does not already provide an ETag
- strong/weak ETag parsing and comparison helpers
- `If-Match`
- `If-None-Match`
- `If-Modified-Since`
- `If-Unmodified-Since`
- server-generated `304 Not Modified`
- server-generated `412 Precondition Failed`

### Range and partial content engine

Implemented:

- `Range: bytes=...`
- single byte-range responses
- multi-range `multipart/byteranges` responses
- `If-Range` handling using ETag or Last-Modified validators
- `206 Partial Content`
- `416 Range Not Satisfiable`
- `Content-Range`
- `Accept-Ranges: bytes`

### Entity metadata closure

Implemented across the direct-response path:

- Content-Length normalization for known final bodies
- HEAD body suppression with preservation of the would-be representation length
- 304 / 412 / 416 metadata closure
- conditional + range interaction ordering
- range-aware H1 / H2 / H3 response behavior
- H1 informational response preservation after moving the normal HTTP/1.1 app-response path onto the buffered entity pipeline

### Content-coding hardening

Retained and exercised with the new entity pipeline:

- gzip negotiation
- Brotli negotiation when Brotli support is available in the runtime
- `Vary: Accept-Encoding`
- content-length replacement after encoding
- deterministic direct-response content-coding behavior

Behavioral note:

- When a request carries a `Range` header, the direct-response pipeline currently processes the response as an **identity representation** and intentionally bypasses dynamic content coding for that request path. This keeps range behavior deterministic and avoids serving slices of dynamically coded payloads.

### Static files

Expanded:

- `StaticFilesApp` now directly supports:
  - generated ETag
  - Last-Modified
  - conditional requests
  - byte ranges
  - HEAD behavior

### Examples

Added:

- `examples/http_entity_static/app.py`
- `examples/http_entity_static/client_http1.py`
- `examples/http_entity_static/public/hello.txt`

These demonstrate a deployable static app plus a matching HTTP/1.1 client for:

- normal GET
- ETag revalidation
- byte ranges
- content-coding observation

## Main modules touched

Primary modified or added modules:

- `src/tigrcorn/http/__init__.py`
- `src/tigrcorn/http/etag.py`
- `src/tigrcorn/http/conditional.py`
- `src/tigrcorn/http/range.py`
- `src/tigrcorn/http/entity.py`
- `src/tigrcorn/static.py`
- `src/tigrcorn/server/runner.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `src/tigrcorn/protocols/http3/handler.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `tests/test_phase2_entity_semantics_checkpoint.py`
- `examples/http_entity_static/app.py`
- `examples/http_entity_static/client_http1.py`
- `docs/review/conformance/PHASE2_CORE_HTTP_ENTITY_SEMANTICS_CHECKPOINT.md`
- `docs/review/conformance/phase2_core_http_entity_semantics_checkpoint.current.json`

## Focused validation completed in this checkpoint

The following focused validation bundle passed:

- `tests/test_phase1_surface_parity_checkpoint.py`
- `tests/test_phase2_entity_semantics_checkpoint.py`
- `tests/test_http1_hardening_pass.py`
- `tests/test_http_content_coding_rfc9110.py`
- `tests/test_response_trailers_rfc9110.py`
- `tests/test_trailers_rfc9110.py`
- `tests/test_server_http1.py`
- `tests/test_server_http2.py`
- `tests/test_http2_rfc9113.py`
- `tests/test_http3_server.py`
- `tests/test_http3_rfc9114.py`

Observed result for that bundle:

- **46 passed**
- **0 failed**

Additional validation completed:

- `python -m compileall -q src/tigrcorn`

## Known partials and remaining gaps

These are still partial or intentionally deferred in this checkpoint:

- Automatic `Last-Modified` generation is implemented for static files, but **generic app responses only honor Last-Modified when the app provides it**.
- The HTTP/1.1 direct app-response path is now **buffered to completion** so Phase 2 entity semantics stay aligned with H2/H3. This is correct for the new entity features, but it is less incremental than a true streaming-first design.
- Dynamic content coding is intentionally bypassed for requests carrying `Range` so that range handling remains deterministic.
- This checkpoint does **not** claim complete RFC 9110 / 7232 / 7233 closure beyond the implemented direct-server behavior in this package snapshot.
- This checkpoint does **not** expand into cache/freshness policy, integrity/trust, or gateway/enforcement product boundaries.

## Practical interpretation

This zip is a strong **Phase 2 checkpoint** with:

- reusable entity-semantics modules
- cross-protocol ETag / conditional / range behavior
- static-file direct support for validators and partial content
- updated examples
- focused protocol validation

It should be treated as:

- a valid checkpoint for continued delivery
- a substantial closure of Phase 2 direct-server semantics
- **not** the final word on the broader “fully featured / fully RFC compliant” expansion program
