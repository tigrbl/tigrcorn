# GitHub issue register

As of 2026-04-03, the `Tigrbl/tigrcorn` GitHub issue set contains 11 researched issues: 10 open issues and 1 closed issue.

Sources used for this note:

- repository remote: `https://github.com/Tigrbl/tigrcorn.git`
- GitHub issue search for `state:open`
- GitHub issue search for `state:closed`
- GitHub per-issue fetch for issues `#11`, `#13`, `#14`, `#15`, `#16`, `#17`, `#18`, `#19`, `#20`, `#21`, and `#22`

This register is a mutable research note. It does not change the package boundary, current-state chain, or promoted release truth. Priority, risk, and disposition fields below are repository assessments inferred from the issue text and the current 0.3.9 governance/boundary documents.

## Portfolio summary

- open issues: 10
- closed issues: 1
- likely duplicate pair: `#14` and `#15`
- dominant theme: test-suite correctness and expectation drift
- boundary-sensitive theme: TLS interoperability on the package-owned TCP/TLS path
- governance-sensitive theme: default-value audit for public CLI/config surface

## Register

### `#11` App loading fails when `--app-dir` is not specified

- state: open
- class: application hosting / CLI correctness
- subsystem: app loading
- boundary relation: in-bounds (`A`, `R`)
- summary: basic `tigrcorn app:app` startup from the current working directory failed because the loader did not place the CWD on `sys.path` unless `--app-dir` was supplied.
- assessment: the issue body states the defect was fixed by PR `#12`, but the issue remains open and should be reconciled against the merged behavior and current tests.
- recommended disposition: verify the fix in current `main`, add or confirm regression coverage, then close if no remaining gap exists.

### `#13` Audit and validate default values across all 124 CLI flags and config model

- state: open
- class: governance / configuration audit
- subsystem: config model, CLI defaults, normalization, docs
- boundary relation: in-bounds (`R`, public operator/API surface)
- summary: requests a structured audit of default values across constants, dataclass defaults, argparse defaults, and normalization-time backfills, with explicit attention to correctness, safety, and consistency.
- assessment: this is the broadest open governance issue and likely the parent issue behind several `None`-driven failures and drift reports in later tickets.
- recommended disposition: treat as an umbrella audit. Split execution into smaller tracked slices if implementation begins, but keep this issue open until the audit artifact, contract alignment, and tests exist.

### `#14` curl/OpenSSL clients fail TLS handshake with custom TLS 1.3 stack

- state: closed
- class: transport / TLS interoperability
- subsystem: TCP/TLS listener path
- boundary relation: in-bounds and certification-sensitive (`T`)
- summary: external OpenSSL-based clients reportedly failed the TLS 1.3 handshake against the custom TLS stack; the issue describes a workaround using stdlib `ssl`.
- assessment: this appears to be superseded by `#15`, which restates the same defect and adds a proposed `--ssl-backend` control. Because the authoritative boundary explicitly depends on package-owned TCP/TLS behavior, any closure rationale should remain honest and evidence-backed.
- recommended disposition: retain as historical duplicate/superseded context only; keep active work on `#15`.

### `#15` curl/OpenSSL clients fail TLS handshake with custom TLS 1.3 stack

- state: open
- class: transport / TLS interoperability
- subsystem: TCP/TLS listener path, CLI/config
- boundary relation: in-bounds and certification-sensitive (`T`)
- summary: active TLS interoperability issue for external OpenSSL clients, with a proposed explicit backend switch between the custom TLS stack and stdlib `ssl`.
- assessment: this is the highest-risk open issue because it touches the package-owned TCP/TLS path called out in the certification boundary. The proposed workaround is practical, but any permanent fix must stay aligned with the published boundary claim.
- recommended disposition: investigate first through the RFC 8446 record-layer path, add OpenSSL 3.5+ `s_client` and curl/OpenSSL peer evidence, and introduce a clearly-scoped stdlib fallback only as an operator control rather than as a replacement certification path.

### `#16` Mirror unittest suite with pytest equivalents and add CI target

- state: open
- class: test infrastructure
- subsystem: tests, CI, developer workflow docs
- boundary relation: in-bounds maintenance
- summary: asks for pytest mirrors of the existing unittest suite plus CI/documentation updates.
- assessment: useful for maintainability, but not a release-line blocker under the current 0.3.9 state. It also creates a risk of mirrored-test drift if introduced mechanically.
- recommended disposition: stage after the more acute correctness failures. Keep parity strict and avoid changing runtime behavior under this ticket.

### `#17` Fix failures in `tests/test_config_matrix_pytest.py`

- state: open
- class: test correctness / configuration validation
- subsystem: config validation, pytest mirror, unittest parity
- boundary relation: in-bounds maintenance with operator-surface relevance
- summary: partial `ServerConfig(...)` instances trigger `TypeError` in `validate_config` because HTTP/2 defaults are missing when the tests expect listener/config validation behavior.
- assessment: tightly related to `#13` and likely symptomatic of the same default/backfill design gap.
- recommended disposition: handle with `#13` in mind. Prefer a single policy for whether validation accepts partial configs or requires normalized defaults.

### `#18` Fix `TypeError` errors in `tests.test_http2_state_machine_completion`

- state: open
- class: protocol correctness / test failure
- subsystem: HTTP/2 handler state initialization
- boundary relation: in-bounds and RFC-sensitive (`P`)
- summary: HTTP/2 completion tests fail because handler comparisons encounter `None` for settings/limits that should be concrete before protocol processing.
- assessment: this is one of the more important open defects after TLS because it lands directly in the in-bounds HTTP/2 protocol surface.
- recommended disposition: investigate whether handler state initialization is incomplete or whether tests bypass required normalization. Fix the underlying invariant rather than sprinkling defensive `None` checks.

### `#19` Fix failing expectation in `tests.test_phase9g_strict_performance_closure`

- state: open
- class: test expectation drift
- subsystem: promotion/performance report tests
- boundary relation: in-bounds maintenance
- summary: the test expects `report.passed` to be `False`, but the observed current report is `True`.
- assessment: likely a stale test expectation rather than a production bug, assuming the current promotion evaluator behavior is intentional.
- recommended disposition: confirm intended promotion-report semantics, then update the assertion or report logic to match the documented current behavior.

### `#20` Fix failing send-path expectation in `tests.test_quic_recovery_live_runtime_integration`

- state: open
- class: protocol/runtime behavior vs test expectation
- subsystem: QUIC recovery runtime integration
- boundary relation: in-bounds and RFC-sensitive (`T`, `P`)
- summary: a live runtime integration test expects one deferred outbound datagram, but the observed queue length is zero.
- assessment: may be expectation drift or a real recovery-path regression. Because it touches QUIC send/recovery behavior, it deserves protocol-level review rather than a test-only patch by default.
- recommended disposition: inspect runtime semantics before editing the test. Close only once the intended blocked-datagram contract is explicit.

### `#21` Fix ALPN empty-string normalization mismatch in `tests.test_security_compat_utils`

- state: open
- class: compatibility behavior / test expectation drift
- subsystem: security compatibility helpers
- boundary relation: in-bounds maintenance on the transport/security edge
- summary: the test expects `normalize_alpn('')` to return `None`, but the implementation returns the empty string.
- assessment: smaller than the main TLS interoperability issue, but it still touches the ALPN policy surface named in the certification boundary.
- recommended disposition: make the empty-input contract explicit in docs/tests and align it with the OpenSSL peer-program ALPN expectations before changing implementation.

### `#22` Fix failing extension-negotiation expectation in `tests.test_websocket_additional_rfc6455`

- state: open
- class: protocol behavior vs test expectation
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
