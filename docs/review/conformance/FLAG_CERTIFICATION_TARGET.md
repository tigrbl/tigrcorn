
# Flag certification target

This target remains subordinate to `docs/review/conformance/STRICT_PROFILE_TARGET.md` for any RFC-scoped strict-promotion claim.
This target document is driven by `docs/review/conformance/flag_contracts.json` and `docs/review/conformance/flag_covering_array.json`.

## Current state

The repository currently exposes **84 public flag strings** in `src/tigrcorn/cli.py`.

The older grouped metadata plane in `cli_flag_surface.json` is still useful as a taxonomy, but it is not sufficient for certifiable per-flag closure.

This checkpoint therefore introduces one contract row per concrete public flag string and a machine-readable covering-array plan that spans all families.

## Contract rules

Every flag contract row carries:

- the concrete public flag string
- the family and claim class
- the resolved config path and default
- value space and disable form
- RFC targets where applicable
- runtime modules, unit tests, interop scenarios, deployment profiles, and performance profiles
- current runtime/evidence status and promotion-readiness state

## Current runtime gaps

There are no remaining public-flag runtime gaps.

All **84** public flag rows are now marked `promotion_ready=true` in `flag_contracts.json`. The remaining promotion blockers now live in strict-target RFC evidence and the stricter performance / promotion-gate work.

## Covering-array rules

`flag_covering_array.json` intentionally does **not** attempt a full cartesian explosion.

It instead requires:

- one-way coverage for every concrete public flag
- one-way coverage for every declared enum value
- explicit three-way hazard clusters for transport/protocol/TLS, protocol/timeout/concurrency, websocket compression by carrier, semantic HTTP extension coverage by version, and workers/reload/inherited-FD interactions

## Claim discipline

- RFC-scoped flags remain bound by the strict target and authoritative boundary files
- hybrid flags must preserve RFC behavior under load, but they are not themselves RFC-defined controls
- pure-operator flags are certified as operator surfaces, not as RFC claims
- non-RFC custom values remain explicitly excluded from RFC compliance claims

## Phase 9A contract freeze

Phase 9A now freezes the remaining family-flag work in:

- `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md`
- `docs/review/conformance/phase9a_execution_backlog.current.json`

The remaining six runtime gaps each now have:

- a frozen owner role
- a module touch list
- a required state transition
- a required unit/performance/deployment coverage contract
- explicit exit tests

Row-level delivery metadata for those seven blockers is now embedded directly in `flag_contracts.json`, while `flag_covering_array.json` records the affected hazard clusters that must remain covered when the flags are closed.


## Phase 9F2 observability closure

Phase 9F2 closes the remaining pure-operator observability runtime gaps for:

- `--log-config`
- `--statsd-host`
- `--otel-endpoint`

Those surfaces are now implemented at runtime, covered by startup/shutdown/failure-mode tests, and no longer count as flag-surface promotion blockers.


## Phase 9F3 concurrency / keepalive closure

Phase 9F3 closes the remaining hybrid/runtime gaps for:

- `--limit-concurrency`
- `--websocket-ping-interval`
- `--websocket-ping-timeout`

Those controls are now implemented at runtime, covered by local closure tests, and no longer count as flag-surface promotion blockers.
