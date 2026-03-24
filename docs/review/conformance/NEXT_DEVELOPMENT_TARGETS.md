
# Next development targets

This program charter is the Phase 8 strict-promotion target document.

It is governed by `docs/review/conformance/CERTIFICATION_BOUNDARY.md` for the current authoritative release claim and by `docs/review/conformance/STRICT_PROFILE_TARGET.md` for the stricter next target.

## Current state at the start of Phase 8

- the current authoritative boundary remains green
- the frozen 0.3.7 root is a candidate only, and should remain frozen
- the next promotable root should be a new release root, not a mutation of 0.3.7
- the repository therefore enters a three-stream closure program rather than a policy-flip checkpoint

No public doc is allowed to strengthen package claims until the strict target is actually green.

## Phase 8 closure streams

1. **strict RFC evidence closure**
   - promote RFC 7692 to independent certification
   - promote RFC 9110 §9.3.6, RFC 9110 §6.5, and RFC 9110 §8 to independent certification
   - promote RFC 6960 to independent certification
   - preserve passing third-party artifacts under a new promotable release root rather than mutating `docs/review/conformance/releases/0.3.7/release-0.3.7/`

2. **family-flag contract/runtime closure**
   - replace grouped flag accounting with row-level contracts in `docs/review/conformance/flag_contracts.json`
   - drive the execution matrix from `docs/review/conformance/flag_covering_array.json`
   - Phase 9F3 has now closed the former runtime gaps for `--limit-concurrency`, `--websocket-ping-interval`, and `--websocket-ping-timeout`

3. **throughput/latency closure with RFC-correctness-under-load**
   - keep the phase6 harness as the component-regression lane
   - add the stricter end-to-end release lane documented in `docs/review/performance/PERFORMANCE_SLOS.md`
   - require correctness-under-load for RFC-scoped and hybrid surfaces before promotion

## Required target artifacts landed in this checkpoint

- `docs/review/conformance/STRICT_PROFILE_TARGET.md`
- `docs/review/conformance/certification_boundary.strict_target.json`
- `docs/review/conformance/FLAG_CERTIFICATION_TARGET.md`
- `docs/review/conformance/flag_contracts.json`
- `docs/review/conformance/flag_covering_array.json`
- `docs/review/performance/PERFORMANCE_SLOS.md`
- `docs/review/performance/performance_slos.json`
- `docs/review/conformance/promotion_gate.target.json`

## Strict-target interpretation rules

- `docs/review/conformance/certification_boundary.json` remains the authoritative current boundary
- `docs/review/conformance/certification_boundary.strict_target.json` is a target boundary, not a current public-claim boundary
- the frozen 0.3.7 root is reused only as the evaluation substrate for the strict target; it is not canonical and it is not promotable
- the next promotable release must be assembled under a new release root after the strict target turns green

## Current blocker summary

The strict target is no longer blocked by missing flag-runtime rows. It is now blocked by the remaining preserved-but-non-passing HTTP/3 `aioquic` strict-target scenarios and the strict performance / promotion-gate work.

Historical Phase 8A start-state summary:

The strict target originally entered this program blocked by 13 missing independent scenarios:

- RFC 7692: `websocket-http11-server-websockets-client-permessage-deflate`, `websocket-http2-server-h2-client-permessage-deflate`, `websocket-http3-server-aioquic-client-permessage-deflate`
- RFC 9110 §9.3.6: `http11-connect-relay-curl-client`, `http2-connect-relay-h2-client`, `http3-connect-relay-aioquic-client`
- RFC 9110 §6.5: `http11-trailer-fields-curl-client`, `http2-trailer-fields-h2-client`, `http3-trailer-fields-aioquic-client`
- RFC 9110 §8: `http11-content-coding-curl-client`, `http2-content-coding-curl-client`, `http3-content-coding-aioquic-client`
- RFC 6960: `tls-server-ocsp-validation-openssl-client`

## Phase-by-phase implementation order

### Phase 8A — documentation and machine-readable targets

Land the dual-boundary model, row-level flag contracts, the covering-array target, performance SLO targets, and the composite promotion target.

### Phase 8B — composite gate implementation

Use `tigrcorn.compat.release_gates.evaluate_promotion_target` to combine:

- authoritative RFC boundary
- strict target boundary
- flag-surface closure
- operator-surface closure
- performance closure
- documentation/claim consistency

### Phase 8C — current-state reporting

Keep the current state explicit in repository docs:

- authoritative boundary remains green
- strict target remains non-green
- promotion remains blocked until the strict target, flag-runtime gaps, and performance SLO targets are all closed

## Phase 9A contract freeze follow-through

The planning ambiguity for the strict-promotion program is now closed in-tree through `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md` and `docs/review/conformance/phase9a_execution_backlog.current.json`.
