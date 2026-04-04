# GitHub issue register matrix

Matrix date: 2026-04-04

The table below summarizes the researched `Tigrbl/tigrcorn` GitHub issue set for quick triage. Classification fields are repository assessments inferred from issue bodies and current boundary/governance docs.

Claim posture used here:

- `implementation claim` — issue affects a shipped implementation claim
- `architectural claim` — issue affects an architecture-level naming or role claim
- `design claim` — issue affects a selected future design target rather than a shipped claim

| Issue | State | Class | Subsystem | Boundary | Risk | Scope | Claim posture affected | Relation | Recommended next action |
|---|---|---|---|---|---|---|---|---|---|
| `#11` | Open | App-load correctness | App loader / CLI | `A,R` | Medium | Narrow | implementation claim | Follow-up after PR `#12` | Verify fix on current `main`, confirm regression test, close if resolved |
| `#13` | Open | Governance audit | Config defaults / CLI / normalize | `R` | High | Broad | implementation claim plus design-claim hygiene | Umbrella for defaults/backfill work | Create audit artifact and explicit default-review plan |
| `#14` | Closed | TLS interoperability | TCP/TLS listener | `T` | High | Narrow | implementation claim | Likely duplicate of `#15` | Keep closed as superseded context |
| `#15` | Open | TLS interoperability | TCP/TLS listener / CLI | `T` | Critical | Medium | implementation claim plus design claim | Successor to `#14`; anchor for atomic RFC 8446/5280/7301 claim rows and OpenSSL 3.5+ peer plan | Execute the atomic TLS matrix starting with RFC 8446 outer framing, inner type, AEAD AAD, padding, and handshake-to-app-data boundary; keep stdlib backend bounded as a differential control only |
| `#16` | Open | Test infrastructure | Pytest mirror / CI | Maintenance | Medium | Large | implementation claim | Independent, but blocked by drift risk | Sequence after correctness fixes |
| `#17` | Open | Test correctness | Config validation / pytest mirror | `R` | High | Medium | implementation claim | Related to `#13` | Decide partial-config validation policy and align tests/code |
| `#18` | Open | Protocol correctness | HTTP/2 handler state | `P` | High | Medium | implementation claim | Possibly related to `#13` backfills | Restore concrete HTTP/2 invariants before handler comparisons |
| `#19` | Open | Expectation drift | Promotion/performance tests | Maintenance | Low | Narrow | implementation claim | Independent | Confirm intended report semantics, then update test or logic |
| `#20` | Open | Runtime/protocol mismatch | QUIC recovery integration | `T,P` | High | Medium | implementation claim | Independent | Inspect runtime semantics before changing test expectations |
| `#21` | Open | Compatibility mismatch | ALPN normalization | `T` | Medium | Narrow | implementation claim | Independent, but adjacent to TLS peer plan | Make empty-input ALPN contract explicit and align it with RFC 7301-facing interop expectations |
| `#22` | Open | Protocol contract mismatch | WebSocket extension negotiation | `P` | High | Narrow | implementation claim | Independent | Define rejection contract, then align test and implementation |

## Matrix views

### By urgency

| Tier | Issues |
|---|---|
| Critical | `#15` |
| High | `#13`, `#17`, `#18`, `#20`, `#22` |
| Medium | `#11`, `#14`, `#16`, `#21` |
| Low | `#19` |

### By boundary area

| Boundary area | Issues |
|---|---|
| `T` transport/security | `#14`, `#15`, `#21` |
| `P` protocol | `#18`, `#22` |
| `T,P` mixed transport/protocol | `#20` |
| `A,R` app/operator | `#11` |
| `R` operator/config | `#13`, `#17` |
| Maintenance / non-boundary-expanding | `#16`, `#19` |

### By probable disposition

| Disposition | Issues |
|---|---|
| Investigate production/runtime defect first | `#15`, `#18`, `#20`, `#22` |
| Audit and policy alignment | `#13`, `#17`, `#21` |
| Likely test expectation update | `#19` |
| Administrative reconcile / close if already fixed | `#11` |
| Historical duplicate / superseded | `#14` |
| Scheduled infrastructure improvement | `#16` |

### By TLS peer-program relevance

| Group | Issues |
|---|---|
| Primary TLS peer-program anchor | `#15` for atomic RFC 8446, RFC 5280, RFC 7301, RFC 6066, RFC 9525, and HTTPS-over-TLS execution rows |
| Adjacent TLS/ALPN cleanup | `#21` |
| Historical duplicate context | `#14` |

### By GitHub state

| State | Issues |
|---|---|
| Open | `#11`, `#13`, `#15`, `#16`, `#17`, `#18`, `#19`, `#20`, `#21`, `#22` |
| Closed | `#14` |

## Roadmap candidate work-item matrix

These are mutable planning work items derived from the roadmap bands. They are not GitHub issues unless and until corresponding issues are opened.

| Work item | Band | Class | Subsystem | Boundary | Risk | Scope | Relation | Recommended next action |
|---|---|---|---|---|---|---|---|---|
| `RM-P1-01` `default` safe baseline | `P1` | Safe deployment profile | Profiles/defaults | `R,D` | High | Medium | Opens the deployment-profile wave | Freeze the baseline profile JSON and audit zero-config defaults against runtime behavior |
| `RM-P1-02` `strict-h1-origin` | `P1` | Safe deployment profile | HTTP/1.1 origin/static/pathsend | `P,D,R` | High | Medium | Depends on profile/default work | Define profile semantics and certify keepalive, redirect-host, and forwarded rejection behavior |
| `RM-P1-03` `strict-h2-origin` | `P1` | Safe deployment profile | HTTP/2/TLS/ALPN origin | `T,P,D,R` | High | Medium | Builds on H1 origin posture | Freeze H2 defaults and add SETTINGS/frame/header bound coverage |
| `RM-P1-04` `strict-h3-edge` | `P1` | Safe deployment profile | QUIC/H3 listener policy | `T,P,R` | Critical | Large | Bridges into QUIC semantic closure | Freeze Retry/resumption/migration posture and prove default 0-RTT denial |
| `RM-P1-05` `strict-mtls-origin` | `P1` | Safe deployment profile | TLS/X.509 client auth | `T,R` | Critical | Medium | Adjacent to TLS peer program | Define SAN/EKU/revocation policy and hard/soft fail behavior |
| `RM-P1-06` `static-origin` | `P1` | Safe deployment profile | Static delivery/origin | `D,R` | High | Medium | Feeds P5 origin contract | Freeze static roots, validators, range, traversal, and symlink posture |
| `RM-P2-01` Base default audit | `P2` | Default audit | Config defaults/normalization | `R` | Critical | Large | Directly related to `#13` and `#17` | Produce the canonical post-normalization default audit and align tests/docs/runtime |
| `RM-P2-02` Profile-effective default audit | `P2` | Default audit | Profile overlays | `R` | High | Medium | Depends on profile definitions | Record effective defaults for each blessed profile and deny unsafe overlay drift |
| `RM-P2-03` Reviewed flag contract registry | `P2` | Governance registry | CLI/help/docs/runtime | `R` | High | Large | Extends the default audit into public controls | Review every public flag row and link risks, claims, and tests |
| `RM-P3-01` Proxy trust model | `P3` | Public policy closure | Proxy normalization | `R,D` | Critical | Medium | Inputs redirect/host safety | Freeze trusted-source semantics and fail-closed behavior |
| `RM-P3-02` Proxy precedence plus normalization | `P3` | Public policy closure | Header precedence | `R,D` | Critical | Medium | Depends on proxy trust model | Freeze `Forwarded` vs `X-Forwarded-*` precedence and conflict handling |
| `RM-P3-03` CONNECT relay policy | `P3` | Public policy closure | CONNECT relay | `P,D,R` | Critical | Medium | One of the highest-risk hidden surfaces | Make allow/deny and anti-abuse posture explicit and preserve a negative corpus |
| `RM-P3-04` Trailer policy | `P3` | Public policy closure | Trailer handling | `P,D` | Medium | Medium | Cross-carrier contract closure | Freeze acceptance/emission semantics across H1/H2/H3 |
| `RM-P3-05` Content-coding policy | `P3` | Public policy closure | Compression/content coding | `P,D` | High | Medium | Tied to static-origin and origin contract work | Freeze negotiation semantics and compressed-range behavior |
| `RM-P3-06` Public controls closure | `P3` | Public policy closure | ALPN/revocation/H2C/WS compression/limits/drain | `T,P,R` | High | Large | Pulls internal controls into public contract | Promote missing controls into CLI/help/docs and add coverage |
| `RM-P4-01` Early-data admission policy | `P4` | QUIC semantic closure | 0-RTT admission | `T,P,R` | Critical | Medium | Depends on strict-h3-edge profile posture | Freeze deny/safe/allowlist/app-mark policy and prove unsafe-method rejection |
| `RM-P4-02` Replay policy | `P4` | QUIC semantic closure | 0-RTT replay handling | `T,P,R` | Critical | Medium | Pairs with admission policy | Define forward/buffer/downgrade/`425` behavior and certify it |
| `RM-P4-03` Multi-instance early-data policy | `P4` | QUIC semantic closure | Anti-replay topology | `T,R` | Critical | Large | Requires honest LB/topology language | Define shared-ticket and multi-node behavior before stronger claims |
| `RM-P4-04` Retry plus app-visible semantics | `P4` | QUIC semantic closure | Retry/app contract | `T,P,A` | High | Medium | Depends on Retry policy closure | Freeze what apps can observe and how invalid/duplicate Retry behaves |
| `RM-P4-05` Independent QUIC state claims | `P4` | QUIC semantic closure | QUIC claim granularity | `T,P,R` | High | Medium | Depends on other P4 closures | Split Retry/resumption/0-RTT/migration/GOAWAY/QPACK into explicit claims |
| `RM-P5-01` Path resolution | `P5` | Origin contract | Static path normalization | `D` | Critical | Medium | Precondition for safe static/pathsend claims | Freeze decode order, dot-segment rules, separators, mounts, and symlinks |
| `RM-P5-02` File selection plus HTTP semantics | `P5` | Origin contract | Static HTTP behavior | `D,P` | High | Medium | Depends on path resolution | Freeze validators, range outcomes, MIME/index/slash rules, and compression interaction |
| `RM-P5-03` ASGI `pathsend` contract | `P5` | Origin contract | Pathsend runtime behavior | `A,D` | High | Medium | Depends on origin semantics | Make stat timing, zero-copy expectations, mid-send mutation, and disconnect handling explicit |
| `RM-P6-01` QUIC/H3 counter families | `P6` | Observability | Metrics schema | `R` | Medium | Medium | Follows semantic closure | Freeze stable counter names and semantics for retry/migration/loss/security |
| `RM-P6-02` Export surfaces | `P6` | Observability | StatsD/DogStatsD/OTEL export | `R` | Medium | Medium | Extends existing observability controls | Make supported export surfaces explicit and add compatibility checks |
| `RM-P6-03` qlog experimental stance | `P6` | Observability | qlog export | `R` | Medium | Medium | Must remain bounded | Mark qlog unstable/versioned/redacted and certify those limits |
| `RM-P7-01` Fail-state registry | `P7` | Negative certification | Reject/close/abort/log semantics | `T,P,D,R` | High | Medium | Governance bridge into corpora work | Freeze expected fail behavior per risky surface |
| `RM-P7-02` Proxy/early-data/QUIC corpora | `P7` | Negative certification | Proxy/QUIC attack suites | `T,P,R` | Critical | Large | Depends on P3/P4 policy closure | Preserve adversarial suites for spoofing, replay, Retry, migration, and amplification pressure |
| `RM-P7-03` Origin/CONNECT/TLS/topology corpora | `P7` | Negative certification | Origin/TLS/topology attack suites | `T,D,R` | Critical | Large | Depends on P3/P5 closure | Preserve traversal, relay abuse, X.509 failure, and mixed-topology negative suites |
| `RM-P8-01` Risk register plus traceability | `P8` | Governance discipline | Risk and claims linkage | Governance | High | Medium | Runs in parallel with P2-P7 | Make risks machine-readable and enforce referential integrity |
| `RM-P8-02` Pytest-only forward motion | `P8` | Governance discipline | Test style policy | Governance | Medium | Medium | Related to `#16` | Make pytest the only forward runner and inventory legacy unittest usage |
| `RM-P8-03` Release-gated evidence plus interop plus perf | `P8` | Governance discipline | Release evidence | Governance | High | Medium | Required before stronger promotion language | Preserve interop, evidence, and perf bundles as release inputs |
| `RM-P8-04` RFC 9651 structured-fields baseline | `P8` | Spec hygiene | Structured fields | `P,R` | High | Medium | Extends current structured-fields candidate work | Replace RFC 8941 baseline references and add round-trip/canonical serialization checks |
