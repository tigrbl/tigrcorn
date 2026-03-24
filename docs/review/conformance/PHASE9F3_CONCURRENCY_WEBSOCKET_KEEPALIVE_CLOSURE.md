# Phase 9F3 concurrency and WebSocket keepalive closure

This checkpoint executes **Phase 9F3** of the Phase 9 implementation plan.

It closes the remaining public runtime gaps for:

- `--limit-concurrency`
- `--websocket-ping-interval`
- `--websocket-ping-timeout`

## What changed

### 1. `--limit-concurrency` is now a real scheduler/runtime control

The repository now treats `--limit-concurrency` as a **global in-flight admission cap** rather than a parse-only config value.

The cap is now enforced across:

- HTTP/1.1 request handling
- HTTP/1.1 CONNECT tunnel admission
- HTTP/1.1 WebSocket session admission
- HTTP/2 request streams
- HTTP/2 CONNECT tunnels
- HTTP/2 WebSocket streams
- HTTP/3 request streams
- HTTP/3 CONNECT tunnels
- HTTP/3 WebSocket streams

When the configured cap is reached, newly admitted work now returns `503 scheduler overloaded` instead of being silently accepted.

### 2. WebSocket keepalive is now a live subsystem

`KeepAlivePolicy` is no longer just a helper object. It now drives real outbound WebSocket keepalive behavior across all supported carriers:

- HTTP/1.1 WebSocket
- HTTP/2 extended CONNECT WebSocket
- HTTP/3 extended CONNECT WebSocket

The runtime now:

- schedules outbound PING frames after the configured idle interval
- tracks pending ping payloads
- acknowledges matching PONG frames
- closes timed-out sessions deterministically with close code `1011` and reason `ping timeout`

### 3. Keepalive and overload metrics are now observable

The metrics surface now records:

- `scheduler_rejections`
- `scheduler_tasks_rejected`
- `websocket_pings_sent`
- `websocket_ping_timeouts`

### 4. The public flag surface is now green

After this checkpoint:

- all **84** public flag rows are promotion-ready
- the flag-surface section of `evaluate_promotion_target()` passes
- the remaining promotion blockers now live only in:
  - preserved-but-non-passing HTTP/3 `aioquic` strict-target scenarios
  - the strict performance target
  - promotion-evaluator hardening / release assembly work still to come

## Honest current result

This checkpoint closes only **9F3**.

What is true now:

- the authoritative boundary remains green
- the strict target remains non-green because preserved HTTP/3 `aioquic` scenarios are still not marked passing
- the flag surface is now **green**
- the operator surface remains green
- the performance target remains non-green
- the composite promotion target remains non-green

So this repository is still **not yet certifiably fully featured** under the stricter promotion target, and it is still **not yet strict-target certifiably fully RFC compliant**.
