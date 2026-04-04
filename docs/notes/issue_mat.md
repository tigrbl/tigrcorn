# GitHub issue register matrix

Matrix date: 2026-04-04

The table below summarizes the researched `Tigrbl/tigrcorn` GitHub issue set for quick triage. Classification fields are repository assessments inferred from issue bodies and current boundary/governance docs.

| Issue | State | Class | Subsystem | Boundary | Risk | Scope | Relation | Recommended next action |
|---|---|---|---|---|---|---|---|---|
| `#11` | Open | App-load correctness | App loader / CLI | `A,R` | Medium | Narrow | Follow-up after PR `#12` | Verify fix on current `main`, confirm regression test, close if resolved |
| `#13` | Open | Governance audit | Config defaults / CLI / normalize | `R` | High | Broad | Umbrella for defaults/backfill work | Create audit artifact and explicit default-review plan |
| `#14` | Closed | TLS interoperability | TCP/TLS listener | `T` | High | Narrow | Likely duplicate of `#15` | Keep closed as superseded context |
| `#15` | Open | TLS interoperability | TCP/TLS listener / CLI | `T` | Critical | Medium | Successor to `#14`; anchor for atomic RFC 8446/5280/7301 claim rows and OpenSSL 3.5+ peer plan | Execute the atomic TLS matrix starting with RFC 8446 outer framing, inner type, AEAD AAD, padding, and handshake-to-app-data boundary; keep stdlib backend bounded as a differential control only |
| `#16` | Open | Test infrastructure | Pytest mirror / CI | Maintenance | Medium | Large | Independent, but blocked by drift risk | Sequence after correctness fixes |
| `#17` | Open | Test correctness | Config validation / pytest mirror | `R` | High | Medium | Related to `#13` | Decide partial-config validation policy and align tests/code |
| `#18` | Open | Protocol correctness | HTTP/2 handler state | `P` | High | Medium | Possibly related to `#13` backfills | Restore concrete HTTP/2 invariants before handler comparisons |
| `#19` | Open | Expectation drift | Promotion/performance tests | Maintenance | Low | Narrow | Independent | Confirm intended report semantics, then update test or logic |
| `#20` | Open | Runtime/protocol mismatch | QUIC recovery integration | `T,P` | High | Medium | Independent | Inspect runtime semantics before changing test expectations |
| `#21` | Open | Compatibility mismatch | ALPN normalization | `T` | Medium | Narrow | Independent, but adjacent to TLS peer plan | Make empty-input ALPN contract explicit and align it with RFC 7301-facing interop expectations |
| `#22` | Open | Protocol contract mismatch | WebSocket extension negotiation | `P` | High | Narrow | Independent | Define rejection contract, then align test and implementation |

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
