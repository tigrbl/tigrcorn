# Tigrcorn Denial of Service Threat Evaluation

Date: 2026-05-05

## Scope

This review evaluates denial-of-service exposure in the current checkout across Tigrcorn's HTTP/1.1, HTTP/2, HTTP/3, QUIC, WebSocket, WebTransport, scheduler, shutdown, static delivery, and observability surfaces. The review used live code, governed SSOT rows, existing conformance evidence, and focused pytest probes.

## Executive Finding

Tigrcorn has an explicit resource-control posture and is not broadly unbounded by default. The implemented protections cover request-head limits, request-body limits, read/write/idle/keepalive timeouts, scheduler admission control, HTTP/2 stream/window settings, WebSocket message and queue caps, QUIC Retry support, QUIC stream limits, HTTP/3 parse-buffer exhaustion, and bounded cancellation during teardown.

The residual DoS exposure is concentrated in four areas:

1. Operator-dependent hardening where limits exist but the safest values are profile/config choices, not universally forced defaults.
2. Protocol surfaces with minimum evidence but incomplete broad independent ecosystem certification, especially QUIC / HTTP/3 flow-control.
3. Application-owned response behavior where Tigrcorn can bound transport resources but cannot prevent expensive ASGI application work.
4. Compression and content-coding surfaces where CPU amplification remains workload-dependent even though negotiation and size policy exist.

## Threat Matrix

| Threat | Surface | Current mitigation | Exposure |
|---|---|---|---|
| Slowloris request head drip | HTTP/1.1 | `read_timeout`, optional `http1_header_read_timeout`, request-head byte limit | Medium if operators leave slow-friendly timeout values in hostile environments |
| Oversized request headers | HTTP/1.1, HTTP/2, HTTP/3 | `max_header_size`, `http1_max_incomplete_event_size`, H2 decoded header cap, H3 field-section cap | Low to medium; H3 depends on configured/advertised limits plus parse-buffer guard |
| Oversized request body | HTTP/1.1, HTTP/2 | `max_body_size` and streaming receive checks | Low for inbound request bodies |
| Chunked transfer drip or huge chunks | HTTP/1.1 | chunk parser enforces total body size; read timeout is applied at server loop | Medium for slow read patterns if timeouts are too generous |
| Scheduler saturation | All request/stream work | `limit_concurrency`, `max_connections`, `max_tasks`, `max_streams`; overload returns 503 | Low when limits are configured; medium if deployers run large defaults without external admission control |
| WebSocket message flood | WebSocket over H1/H2/H3 | `websocket.max_message_size`, `websocket.max_queue`, ping timeout | Low to medium; compression-enabled workloads can still be CPU sensitive |
| WebSocket idle connection hoarding | WebSocket | configurable ping interval/timeout | Medium when heartbeat is disabled or too loose |
| HTTP/2 stream flood | HTTP/2 | `MAX_CONCURRENT_STREAMS`, scheduler stream/work caps, read timeout | Low to medium; needs continued interop coverage for hostile peers |
| HTTP/2 flow-control abuse | HTTP/2 | stream and connection windows exist | Medium; implementation evidence exists, but stress certification should stay current |
| QUIC initial packet amplification | QUIC / HTTP/3 | `quic.require_retry`, strict H3 profile requires Retry | Medium by default because default profile does not force Retry; low in strict H3 edge profile |
| QUIC / HTTP/3 stream and control pressure | QUIC / HTTP/3 | stream caps, idle timeout, H3 parse-buffer cap, GOAWAY handling | Medium; broad ecosystem flow-control certification remains incomplete |
| WebTransport session/stream flood | WebTransport | `webtransport.max_streams`, H3/QUIC stream limits, queue-backed receive | Medium; `max_sessions` and `max_streams` are optional and should be fixed in exposed deployments |
| CONNECT relay abuse | HTTP/2, HTTP/3 CONNECT | default `connect_policy` is deny; allowlist validation exists | Low by default; medium only if relay is enabled with broad allowlist |
| Static file range abuse | Static delivery | range handling and content-coding bypass for range determinism | Low to medium; filesystem and caching posture still matter |
| Compression CPU amplification | response content-coding, permessage-deflate | explicit policy and off-by-default WebSocket compression | Medium when compression is enabled for attacker-controlled high-volume traffic |
| Teardown hang | server shutdown / scheduler | bounded cancellation contract reports pending teardown | Low; resistant tasks are reported instead of hanging silently |

## Tested Hypotheses

| Hypothesis | Probe | Result |
|---|---|---|
| H3 incomplete request-frame buffering fails closed at a configured cap | `tests/test_dos_resilience.py::test_http3_request_parse_buffer_exhaustion_fails_closed` | Pass |
| HTTP/1.1 oversized request heads fail closed before request acceptance | `tests/test_dos_resilience.py::test_http11_request_head_limit_fails_closed` | Pass |
| WebSocket upgrade request heads fail closed before upgrade acceptance | `tests/test_dos_resilience.py::test_websocket_upgrade_request_head_limit_fails_closed` | Pass |
| WebSocket oversized frames fail before payload acceptance | `tests/test_dos_resilience.py::test_websocket_oversized_frame_fails_before_payload_acceptance` | Pass |
| Cancellation-resistant tasks cannot silently hang shutdown forever | `tests/test_dos_resilience.py::test_bounded_cancellation_reports_pending_teardown` and `test_taskset_bounded_cancellation_uses_same_teardown_contract` | Pass |
| DoS resilience is governed in generated SSOT | `tests/test_dos_resilience.py::test_dos_resilience_is_governed_in_generated_ssot` | Pass |
| Scheduler admission and keepalive behavior are enforced across H1/H2/H3 WebSocket paths | `tests/test_concurrency_keepalive_closure.py` | Pass |
| Operator CLI/config surfaces expose resource knobs | `tests/test_h1_websocket_operator_surface.py`, `tests/test_http2_operator_surface.py`, `tests/test_flow_scheduler.py` | Pass |

Focused verification command:

```powershell
$env:UV_CACHE_DIR='E:\swarmauri_github\tigrcorn\.tmp\uv-cache'; uv run pytest tests/test_dos_resilience.py tests/test_concurrency_keepalive_closure.py tests/test_h1_websocket_operator_surface.py tests/test_http2_operator_surface.py tests/test_flow_scheduler.py
```

Observed result:

```text
37 passed in 3.18s
```

After adding the two new probes:

```powershell
$env:UV_CACHE_DIR='E:\swarmauri_github\tigrcorn\.tmp\uv-cache'; uv run pytest tests/test_dos_resilience.py
```

Observed result:

```text
8 passed in 0.59s
```

## Evidence Notes

- Default limits include 16 MiB body and WebSocket message caps, 64 KiB header caps, 128 HTTP/2 concurrent streams, 32 WebSocket queue entries, 30 second read/write/idle defaults, and 5 second keepalive.
- HTTP/1.1 request heads are bounded by the smaller of `max_header_size` and `http1_max_incomplete_event_size`.
- HTTP/1.1 request bodies and chunked bodies are rejected when total bytes exceed `max_body_size`.
- HTTP/2 and HTTP/3 overload paths return 503 `scheduler overloaded` when work admission fails.
- HTTP/3 request stream parse buffers abandon the stream and raise `H3_EXCESSIVE_LOAD` after the configured parse-buffer limit.
- Strict H3 edge profile requires QUIC Retry and denies early data, but the default profile leaves Retry disabled.
- Flow-control documentation honestly states that broad QUIC / HTTP/3 ecosystem certification is still not finished, while minimum independent evidence exists.

## Recommended Hardening

1. For internet-exposed deployments, set explicit limits instead of relying on broad defaults: `--limit-concurrency`, `--max-connections`, `--max-tasks`, `--max-streams`, `--max-body-size`, `--max-header-size`, `--http1-header-read-timeout`, `--websocket-max-message-size`, `--websocket-max-queue`, and `--idle-timeout`.
2. Enable WebSocket ping interval and ping timeout for public long-lived connection surfaces.
3. Use the strict H3 edge profile or explicitly enable `--quic-require-retry` for public UDP/H3 exposure.
4. Keep CONNECT relay disabled unless a narrow allowlist and negative relay corpus are part of deployment certification.
5. Treat WebSocket compression and response content-coding as capacity-planning surfaces; benchmark CPU pressure with representative payloads before enabling them broadly.
6. Expand independent hostile-peer QUIC / HTTP/3 flow-control evidence beyond the current minimum bundle.
7. Add live slow-client tests for HTTP/1.1 chunk drip, WebSocket idle-hoarding, and H3 control-stream pressure in addition to the current unit-level resource probes.
