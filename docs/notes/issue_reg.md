# GitHub issue register

As of 2026-04-04, the `Tigrbl/tigrcorn` GitHub issue set contains 11 researched issues: 10 open issues and 1 closed issue.

Sources used for this note:

- repository remote: `https://github.com/Tigrbl/tigrcorn.git`
- GitHub issue search for `state:open`
- GitHub issue search for `state:closed`
- GitHub per-issue fetch for issues `#11`, `#13`, `#14`, `#15`, `#16`, `#17`, `#18`, `#19`, `#20`, `#21`, and `#22`

This register is a mutable research note. It does not change the package boundary, current-state chain, or promoted release truth. Priority, risk, and disposition fields below are repository assessments inferred from the issue text and the current 0.3.9 governance/boundary documents.

Claim posture used in this register:

- `implementation claim` — issue affects a shipped implementation claim
- `architectural claim` — issue affects an architecture-level naming or role claim
- `design claim` — issue affects a selected future design target rather than a shipped claim

## Portfolio summary

- open issues: 10
- closed issues: 1
- likely duplicate pair: `#14` and `#15`
- dominant theme: test-suite correctness and expectation drift
- boundary-sensitive theme: TLS interoperability on the package-owned TCP/TLS path
- governance-sensitive theme: default-value audit for public CLI/config surface
- primary claim posture affected: implementation claims, with secondary design-claim hygiene for planned target waves

## Register

### `#11` App loading fails when `--app-dir` is not specified

- state: open
- class: application hosting / CLI correctness
- claim posture affected: implementation claim
- subsystem: app loading
- boundary relation: in-bounds (`A`, `R`)
- summary: basic `tigrcorn app:app` startup from the current working directory failed because the loader did not place the CWD on `sys.path` unless `--app-dir` was supplied.
- assessment: the issue body states the defect was fixed by PR `#12`, but the issue remains open and should be reconciled against the merged behavior and current tests.
- recommended disposition: verify the fix in current `main`, add or confirm regression coverage, then close if no remaining gap exists.

### `#13` Audit and validate default values across all 124 CLI flags and config model

- state: open
- class: governance / configuration audit
- claim posture affected: implementation claim plus design-claim hygiene
- subsystem: config model, CLI defaults, normalization, docs
- boundary relation: in-bounds (`R`, public operator/API surface)
- summary: requests a structured audit of default values across constants, dataclass defaults, argparse defaults, and normalization-time backfills, with explicit attention to correctness, safety, and consistency.
- assessment: this is the broadest open governance issue and likely the parent issue behind several `None`-driven failures and drift reports in later tickets.
- recommended disposition: treat as an umbrella audit. Split execution into smaller tracked slices if implementation begins, but keep this issue open until the audit artifact, contract alignment, and tests exist.

### `#14` curl/OpenSSL clients fail TLS handshake with custom TLS 1.3 stack

- state: closed
- class: transport / TLS interoperability
- claim posture affected: implementation claim
- subsystem: TCP/TLS listener path
- boundary relation: in-bounds and certification-sensitive (`T`)
- summary: external OpenSSL-based clients reportedly failed the TLS 1.3 handshake against the custom TLS stack; the issue describes a workaround using stdlib `ssl`.
- assessment: this appears to be superseded by `#15`, which restates the same defect and adds a proposed `--ssl-backend` control. Because the authoritative boundary explicitly depends on package-owned TCP/TLS behavior, any closure rationale should remain honest and evidence-backed.
- recommended disposition: retain as historical duplicate/superseded context only; keep active work on `#15`.

### `#15` curl/OpenSSL clients fail TLS handshake with custom TLS 1.3 stack

- state: open
- class: transport / TLS interoperability
- claim posture affected: implementation claim plus design claim
- subsystem: TCP/TLS listener path, CLI/config
- boundary relation: in-bounds and certification-sensitive (`T`)
- summary: active TLS interoperability issue for external OpenSSL clients, with a proposed explicit backend switch between the custom TLS stack and stdlib `ssl`.
- assessment: this is the highest-risk open issue because it touches the package-owned TCP/TLS path called out in the certification boundary. The proposed workaround is practical, but any permanent fix must stay aligned with the published boundary claim. The current execution model should be atomic: one RFC target plus one concrete subfeature requirement per claim row.
- recommended disposition: execute `#15` through atomic rows rather than a single broad TLS item. Start with RFC 8446 protected record outer framing, inner content type recovery, AEAD additional data construction, padding semantics, and handshake-to-application-data boundary; then close RFC 5280 cert-profile/path-validation rows and RFC 7301 ALPN rows with preserved OpenSSL 3.5+ and curl/OpenSSL evidence. Keep the stdlib backend as a clearly-scoped differential control, not a replacement certification path.

#### `#15` atomic execution rows

- RFC 8446 protected record outer framing
- RFC 8446 inner content type recovery
- RFC 8446 AEAD additional data construction
- RFC 8446 padding semantics
- RFC 8446 handshake-to-application-data boundary
- RFC 8446 alert emission and close semantics
- RFC 8446 Certificate and CertificateVerify processing
- RFC 7301 ALPN negotiation policy
- RFC 6066 SNI handling
- RFC 6066 OCSP stapling request handling
- RFC 5280 AKI/SKI handling
- RFC 5280 KeyUsage and ExtendedKeyUsage correctness
- RFC 5280 path validation correctness
- RFC 6960 hard-fail/soft-fail OCSP policy
- RFC 9525 service identity and hostname verification compatibility
- RFC 9112 HTTPS over HTTP/1.1 interoperability
- RFC 9113 HTTP/2 over TLS posture
- RFC 9001 QUIC-TLS mapping parity
- RFC 9000 Retry and token-integrity dependence on TLS-derived state
- RFC 9114 HTTP/3 control-plane correctness after external TLS-backed QUIC handshakes
- RFC 9204 QPACK pressure and decode-failure handling after stable H3 establishment

### `#16` Mirror unittest suite with pytest equivalents and add CI target

- state: open
- class: test infrastructure
- claim posture affected: implementation claim
- subsystem: tests, CI, developer workflow docs
- boundary relation: in-bounds maintenance
- summary: asks for pytest mirrors of the existing unittest suite plus CI/documentation updates.
- assessment: useful for maintainability, but not a release-line blocker under the current 0.3.9 state. It also creates a risk of mirrored-test drift if introduced mechanically.
- recommended disposition: stage after the more acute correctness failures. Keep parity strict and avoid changing runtime behavior under this ticket.

### `#17` Fix failures in `tests/test_config_matrix_pytest.py`

- state: open
- class: test correctness / configuration validation
- claim posture affected: implementation claim
- subsystem: config validation, pytest mirror, unittest parity
- boundary relation: in-bounds maintenance with operator-surface relevance
- summary: partial `ServerConfig(...)` instances trigger `TypeError` in `validate_config` because HTTP/2 defaults are missing when the tests expect listener/config validation behavior.
- assessment: tightly related to `#13` and likely symptomatic of the same default/backfill design gap.
- recommended disposition: handle with `#13` in mind. Prefer a single policy for whether validation accepts partial configs or requires normalized defaults.

### `#18` Fix `TypeError` errors in `tests.test_http2_state_machine_completion`

- state: open
- class: protocol correctness / test failure
- claim posture affected: implementation claim
- subsystem: HTTP/2 handler state initialization
- boundary relation: in-bounds and RFC-sensitive (`P`)
- summary: HTTP/2 completion tests fail because handler comparisons encounter `None` for settings/limits that should be concrete before protocol processing.
- assessment: this is one of the more important open defects after TLS because it lands directly in the in-bounds HTTP/2 protocol surface.
- recommended disposition: investigate whether handler state initialization is incomplete or whether tests bypass required normalization. Fix the underlying invariant rather than sprinkling defensive `None` checks.

### `#19` Fix failing expectation in `tests.test_phase9g_strict_performance_closure`

- state: open
- class: test expectation drift
- claim posture affected: implementation claim
- subsystem: promotion/performance report tests
- boundary relation: in-bounds maintenance
- summary: the test expects `report.passed` to be `False`, but the observed current report is `True`.
- assessment: likely a stale test expectation rather than a production bug, assuming the current promotion evaluator behavior is intentional.
- recommended disposition: confirm intended promotion-report semantics, then update the assertion or report logic to match the documented current behavior.

### `#20` Fix failing send-path expectation in `tests.test_quic_recovery_live_runtime_integration`

- state: open
- class: protocol/runtime behavior vs test expectation
- claim posture affected: implementation claim
- subsystem: QUIC recovery runtime integration
- boundary relation: in-bounds and RFC-sensitive (`T`, `P`)
- summary: a live runtime integration test expects one deferred outbound datagram, but the observed queue length is zero.
- assessment: may be expectation drift or a real recovery-path regression. Because it touches QUIC send/recovery behavior, it deserves protocol-level review rather than a test-only patch by default.
- recommended disposition: inspect runtime semantics before editing the test. Close only once the intended blocked-datagram contract is explicit.

### `#21` Fix ALPN empty-string normalization mismatch in `tests.test_security_compat_utils`

- state: open
- class: compatibility behavior / test expectation drift
- claim posture affected: implementation claim
- subsystem: security compatibility helpers
- boundary relation: in-bounds maintenance on the transport/security edge
- summary: the test expects `normalize_alpn('')` to return `None`, but the implementation returns the empty string.
- assessment: smaller than the main TLS interoperability issue, but it still touches the ALPN policy surface named in the certification boundary.
- recommended disposition: make the empty-input contract explicit in docs/tests and align it with the OpenSSL peer-program ALPN expectations before changing implementation.

### `#22` Fix failing extension-negotiation expectation in `tests.test_websocket_additional_rfc6455`

- state: open
- class: protocol behavior vs test expectation
- claim posture affected: implementation claim
- subsystem: WebSocket extension negotiation
- boundary relation: in-bounds and RFC-sensitive (`P`)
- summary: a test expects `RuntimeError` during extension negotiation rejection, but no exception is raised.
- assessment: likely a behavior-contract mismatch. Because RFC 6455 is part of the boundary, the intended rejection semantics should be stated before changing code or tests.
- recommended disposition: determine the correct API/runtime contract for unsupported extension negotiation, then align tests and implementation to that contract.

## Suggested working order

1. `#15` because it is certification-sensitive and impacts external interoperability on the package-owned TLS path.
2. `#18` because it lands inside the core HTTP/2 protocol surface.
3. `#13` as the umbrella default-value audit that can prevent more `None`-driven defects.
4. `#17` because it appears downstream of the default/normalization policy gap.
5. `#20` and `#22` because they may be substantive protocol-contract mismatches.
6. `#19` and `#21` because they look comparatively contained.
7. `#16` once correctness and contract issues have stabilized.
8. `#11` administrative close-out after confirming the fix remains correct.
9. `#14` keep closed as superseded duplicate context unless evidence shows otherwise.

## Cross-issue relationships

- `#14` is likely superseded by `#15`.
- `#13` is the umbrella issue most clearly related to `#17` and possibly part of `#18`.
- `#19`, `#20`, `#21`, and `#22` all show a pattern of test expectation drift versus current runtime/report behavior.
- `#15`, `#18`, `#20`, and `#22` are the most boundary-sensitive technical issues because they directly affect transport/protocol behavior.

## Canonical researched issue set

The current researched GitHub issue set for this note is:

- open: `#11`, `#13`, `#15`, `#16`, `#17`, `#18`, `#19`, `#20`, `#21`, `#22`
- closed: `#14`

## Roadmap-derived candidate work register

The roadmap now adds 33 mutable planning work items. They are backlog candidates for future execution and should not be treated as opened GitHub issues until they are filed.

### By band

| Band | Candidate work items |
|---|---|
| `P1` | `RM-P1-01` through `RM-P1-06` for safe deployment profiles |
| `P2` | `RM-P2-01` through `RM-P2-03` for default audits and flag-contract truth |
| `P3` | `RM-P3-01` through `RM-P3-06` for proxy/public-policy closure |
| `P4` | `RM-P4-01` through `RM-P4-05` for QUIC semantic closure |
| `P5` | `RM-P5-01` through `RM-P5-03` for origin delivery contract closure |
| `P6` | `RM-P6-01` through `RM-P6-03` for observability closure |
| `P7` | `RM-P7-01` through `RM-P7-03` for negative-certification closure |
| `P8` | `RM-P8-01` through `RM-P8-04` for governance discipline and RFC 9651 hygiene |

### Candidate register

| Work item | Summary | Recommended disposition |
|---|---|---|
| `RM-P1-01` | Freeze the zero-config safe baseline profile and prove safe defaults by default | open first if profile work begins |
| `RM-P1-02` | Freeze conservative HTTP/1.1 origin semantics, proxy normalization, and pathsend posture | open after baseline profile scaffolding exists |
| `RM-P1-03` | Freeze auditable HTTP/2 origin posture with TLS, ALPN, and SETTINGS bounds | open with H2 profile bundle and cap tests |
| `RM-P1-04` | Freeze QUIC/H3 edge posture with Retry, migration, resumption, and default 0-RTT denial | open as the first H3 operating-mode issue |
| `RM-P1-05` | Freeze repeatable mTLS origin posture with SAN/EKU and revocation policy | open beside TLS/X.509 operator docs work |
| `RM-P1-06` | Freeze static-origin profile rules for roots, validators, ranges, and traversal denial | open with origin contract planning |
| `RM-P2-01` | Audit all post-normalization zero-config defaults across the public surface | treat as umbrella execution issue for defaults |
| `RM-P2-02` | Audit effective defaults after each blessed profile overlay | open after P1 profile definitions stabilize |
| `RM-P2-03` | Review every public flag/default row and link risks, claims, and tests | open as the public control registry issue |
| `RM-P3-01` | Freeze trusted proxy-source semantics and fail-closed behavior | open before any precedence work |
| `RM-P3-02` | Freeze `Forwarded` versus `X-Forwarded-*` precedence and conflict handling | open after trust model decisions are written |
| `RM-P3-03` | Make CONNECT relay posture explicit and preserve negative anti-abuse evidence | open as a high-risk policy issue |
| `RM-P3-04` | Freeze trailer semantics across H1/H2/H3 | open as a cross-carrier contract issue |
| `RM-P3-05` | Freeze content-coding negotiation and compressed-range behavior | open with origin/static interaction coverage |
| `RM-P3-06` | Promote ALPN, revocation, H2C, WS compression, limits, and drain controls into reviewed public controls | open once default and flag audits exist |
| `RM-P4-01` | Freeze 0-RTT admission policy variants and unsafe-method rejection | open after strict-h3-edge posture work |
| `RM-P4-02` | Freeze replay handling semantics including downgrade and `425` behavior | open beside 0-RTT admission policy |
| `RM-P4-03` | Define multi-instance anti-replay behavior and LB-specific honesty rules | open only with explicit topology notes |
| `RM-P4-04` | Freeze Retry interaction and application-visible semantics | open after Retry/runtime semantics are reviewed |
| `RM-P4-05` | Split QUIC claims into Retry, resumption, 0-RTT, migration, and GOAWAY/QPACK rows | open after P4 behavior rows exist |
| `RM-P5-01` | Freeze path decoding and normalization rules for static delivery and pathsend | open first in the origin contract wave |
| `RM-P5-02` | Freeze file selection, validators, range outcomes, and compression interaction | open after path resolution decisions are fixed |
| `RM-P5-03` | Make the ASGI `pathsend` runtime contract explicit | open with origin docs and race-condition tests |
| `RM-P6-01` | Freeze stable QUIC/H3 counter families for operators | open after QUIC semantics are explicit |
| `RM-P6-02` | Make StatsD/DogStatsD and OTEL export surfaces explicit supported controls | open after counter schema work |
| `RM-P6-03` | Bound qlog as unstable, versioned, and redacted experimental export | open only with explicit non-claim language |
| `RM-P7-01` | Freeze fail-state behavior by risky surface | open before or alongside negative corpora preservation |
| `RM-P7-02` | Preserve proxy/early-data/QUIC adversarial suites | open after policy rows in P3/P4 are written |
| `RM-P7-03` | Preserve origin/CONNECT/TLS/topology adversarial suites | open after origin and CONNECT policy rows are written |
| `RM-P8-01` | Make risks machine-readable and traceable to claims/tests/evidence | open in parallel with P2-P7 work |
| `RM-P8-02` | Move forward motion to pytest-only and inventory legacy unittest | open with test-style governance work |
| `RM-P8-03` | Make evidence, interop, and perf bundles release-gated inputs | open before stronger promotion claims |
| `RM-P8-04` | Replace RFC 8941 baseline references with RFC 9651 and add conformance checks | open in parallel with governance and field work |

## Roadmap synchronization note

The roadmap-derived `RM-*` planning rows in this register are synchronized with `F-*` feature rows in `docs/notes/feature_reg.md`, grouped `R-*` risk rows in `docs/notes/risk_reg.md`, and machine-readable `TC-ROADMAP-*` candidate claims in `docs/review/conformance/claims_registry.json`.
