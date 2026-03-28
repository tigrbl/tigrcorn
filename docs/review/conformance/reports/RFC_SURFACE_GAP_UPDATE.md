# tigrcorn 0.3.6 surface-gap update

## What was addressed

This update closes the remaining issue quoted for the HTTP/2 carrier:

- outbound HTTP/2 server push is now supported on the server side
- `PUSH_PROMISE` plus promised response streams are emitted on server-initiated even-numbered streams
- client-originated `PUSH_PROMISE` frames continue to be rejected
- the request-side push toggle follows the client's `SETTINGS_ENABLE_PUSH`
- promised streams now use explicit `reserved-local` / `half-closed-remote` lifecycle transitions

The previously quoted WebSocket denial-body limitation on the HTTP/2 and HTTP/3 carriers was already fixed in the supplied archive and remains covered by tests in this updated archive.

## Files changed

Modified:
- `src/tigrcorn/protocols/http2/codec.py`
- `src/tigrcorn/protocols/http2/state.py`
- `src/tigrcorn/protocols/http2/streams.py`
- `src/tigrcorn/protocols/http2/handler.py`
- `docs/protocols/http2.md`
- `docs/review/conformance/reports/RFC_HARDENING_REPORT.md`
- `tests/test_http2_state_machine_completion.py`

Added:
- `tests/test_http2_server_push_surface.py`

## Validation

- targeted HTTP/2 surface tests: passed
- full suite: `241 passed, 2 skipped`

## Certification note

This update closes the quoted HTTP/2 surface-coverage gap in code and tests.

It still would not be honest to label the package **certifiably fully RFC compliant** from this archive alone, because the remaining package-level certification boundary is preserved independent-peer evidence for broader HTTP/3 / WebSocket-over-HTTP/3 interoperability rather than this HTTP/2 feature surface.
