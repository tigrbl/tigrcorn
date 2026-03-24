# Performance boundary

Performance closure is **not** an RFC claim. It is a release-certified product claim.

The repository treats performance evidence as a separate boundary with its own preserved artifacts, profile definitions, thresholds, regression budgets, lanes, and deployment-profile linkage.

## What this boundary proves

For every required profile in `performance_matrix.json`, the repository preserves:

- `result.json`
- `summary.json`
- `env.json`
- percentile histogram data
- raw sample CSV
- command metadata
- profile id and lane metadata
- threshold pass/fail evaluation
- relative regression evaluation
- correctness-under-load checks when the profile exercises an RFC-scoped feature

## Policy

A performance profile is considered passing only when all of the following are true:

1. it meets the **absolute thresholds** declared in `performance_matrix.json`
2. it stays within the **relative regression budget** when compared to the accepted baseline artifact root
3. its **correctness-under-load** checks pass when the profile exercises an RFC-scoped or RFC-sensitive surface

## Preserved roots in this checkpoint

This checkpoint preserves two roots:

- `docs/review/performance/artifacts/phase6_reference_baseline/`
- `docs/review/performance/artifacts/phase6_current_release/`

The baseline root is the accepted reference lane for this checkpoint.
The current-release root is the candidate lane evaluated against that baseline.

## Scope of the harness

The current harness remains package-owned performance evidence. It is suitable for **repeatable release gating**, but it does **not** claim independent third-party performance certification.

## Families required in this checkpoint

- HTTP
- WebSocket
- TLS / PKI
- semantic extras (CONNECT / trailers / content coding)
- operator overhead (logging / metrics / proxy / worker / drain / reload)

## Deployment-profile linkage

Every performance profile names a deployment profile from `docs/review/conformance/deployment_profiles.json`.
That linkage is how performance claims stay tied to concrete server surfaces instead of becoming a hand-wavy global claim.

## Strict-promotion target overlay

`PERFORMANCE_SLOS.md` and `performance_slos.json` define the stricter next target for throughput / latency closure.

After the Phase 9G checkpoint, the **performance section** of the composite promotion evaluator is green.
The overall promotion target is still blocked by preserved-but-non-passing HTTP/3 `aioquic` independent evidence and later plan phases.
