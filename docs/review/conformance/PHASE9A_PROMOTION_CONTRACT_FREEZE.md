# Phase 9A promotion-contract freeze

This checkpoint executes **Phase 9A** of `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`.

It freezes the promotion contract before heavier implementation starts. It is **not** a claim that the current tree is already certifiably fully featured or strict-target complete.

## Current machine-readable result

- authoritative boundary: `True`
- strict target boundary: `False`
- flag surface: `False`
- operator surface: `True`
- performance target: `False`
- documentation / claim consistency: `True`
- composite promotion gate: `False`

## Release-root policy frozen in this checkpoint

- the authoritative release evidence still lives under `docs/review/conformance/releases/0.3.6/release-0.3.6/`
- the frozen candidate root `docs/review/conformance/releases/0.3.7/release-0.3.7/` remains **immutable**
- the next promotable root is now explicitly reserved as `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- no work in this phase changes the current release-gate truth; it only freezes the execution contract and reserves the next release path

## Backlog frozen in this checkpoint

A tracked backlog now exists for every remaining blocker family:

- **13 strict-target independent-scenario gaps** in `docs/review/conformance/phase9a_execution_backlog.current.json`
- **7 public flag/runtime gaps** in `docs/review/conformance/phase9a_execution_backlog.current.json`
- **strict performance and gate-hardening contracts** in the same machine-readable backlog file

Every remaining blocker now has:

- an owner role
- a target phase
- a module/file touch list
- an artifact contract
- an exit-test definition

## Exact performance contract frozen from `performance_slos.json`

The strict performance target is now frozen as:

- required metric keys: `throughput_ops_per_sec, p50_ms, p95_ms, p99_ms, p99_9_ms, time_to_first_byte_ms, handshake_latency_ms, error_rate, scheduler_rejections, protocol_stalls, cpu_seconds, rss_kib`
- required threshold keys: `min_throughput_ops_per_sec, max_p50_ms, max_p95_ms, max_p99_ms, max_p99_9_ms, max_time_to_first_byte_ms, max_handshake_latency_ms, max_error_rate, max_scheduler_rejections, max_protocol_stalls, max_rss_kib`
- required relative-regression budget keys: `max_throughput_drop_fraction, max_p99_increase_fraction, max_p99_9_increase_fraction, max_cpu_increase_fraction, max_rss_increase_fraction`
- required artifact files: `summary.json, index.json, result.json, env.json, percentile_histogram.json, raw_samples.csv, command.json, correctness.json`
- required lanes: `component_regression, end_to_end_release`

Those sets are part of the promotion contract for the remaining performance and evaluator phases. They are not advisory.

## Operator no-regression rule frozen

The operator surface is already green against the frozen operator bundle and must not regress while the remaining strict-target work lands.

Required operator keys remain:

- `workers_process_supervision`
- `reload`
- `proxy_header_normalization`
- `root_path_scope_injection`
- `structured_logging`
- `metrics_endpoint`
- `resource_timeout_controls_wired`

## Explicitly out of scope for the promotion-critical path

Until the strict target is actually green, the following remain outside the promotion-critical path:

- `RFC 7232`
- `RFC 9530`
- `RFC 9111`
- `RFC 9421`
- `JOSE`
- `COSE`

Those items remain valid follow-on work, but they are not allowed to dilute or redefine the current strict-promotion contract.

## Honest current state

This phase does **not** make the repository strict-target complete.

After the contract freeze:

- the package remains **certifiably fully RFC compliant under the authoritative certification boundary**
- the package is **not yet** certifiably fully featured under the stricter Phase 8 / Phase 9 promotion target
- the remaining blocker families are still:
  - 13 missing independent third-party strict-target scenarios
  - 7 non-promotion-ready public flags
  - stricter performance / evaluator closure work

See `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md` and `docs/review/conformance/phase9a_execution_backlog.current.json` for the row-level execution backlog.
