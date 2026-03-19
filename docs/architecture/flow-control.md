# Flow control

Flow control is a first-class concern.

The package tree contains modules for:

- backpressure accounting
- buffer limits
- watermarks
- credits
- timeouts
- keepalive policy

Concrete paths in this archive now use those concerns in more than one place:

- HTTP/1.1 request bodies stream incrementally onto ASGI receive events
- HTTP/2 connection and stream send windows are enforced
- the QUIC transport tracks connection and stream credit

Broad independent QUIC / HTTP/3 flow-control certification is still incomplete, but the archive now preserves a formal review bundle under
`docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-provisional-flow-control-gap-bundle/`.
That bundle is explicitly non-certifying; it maps same-stack HTTP/3 replay artifacts and local flow-control vectors into a stable review root so the remaining gap is concrete and inspectable.
See `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md` for the current state.
