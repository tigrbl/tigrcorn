# Trailer fields local behavior artifacts

This document records the local behavior vectors preserved during **Phase 9D2**.

Artifact bundle:

- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-trailer-fields-local-behavior-artifacts/`

The preserved vectors are:

- `http11-request-trailers-pass`
- `http11-request-trailers-drop`
- `http11-request-trailers-strict-invalid`
- `http11-response-trailers-pass`
- `http2-request-trailers-pass`
- `http2-request-trailers-strict-invalid`
- `http2-response-trailers-pass`
- `http3-request-trailers-pass`
- `http3-request-trailers-strict-invalid`
- `http3-response-trailers-pass`

These vectors are not part of the independent-certification proof tier. They preserve local behavioral evidence for request-trailer pass/drop/strict semantics, response-trailer framing, and ASGI trailer-event exposure while the strict independent path is being completed.
