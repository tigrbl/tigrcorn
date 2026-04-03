# Risk register

Date: 2026-04-03

This is a mutable working risk register derived from the current issue register, issue matrix, feature matrix, TLS/OpenSSL peer plan, and the current certification-boundary evidence tiers.

This note does not widen the current package boundary. It is a working governance aid for selecting and sequencing future work.

## Active risks

| risk_id | title | severity | related issues | related targets | affected standards / policy | current concern | mitigation direction |
|---|---|---|---|---|---|---|---|
| `R-TLS-8446-OPENSSL35` | Custom TLS 1.3 fails strict external TCP/TLS peers | critical | `#15`, `#14` | Wave 1A TLS RFC and OpenSSL 3.5+ targets | RFC 8446; RFC 7301; RFC 5280; RFC 9525 | OpenSSL 3.5+ peers may reject the custom TLS record layer with `bad record type` and block honest external TCP/TLS interoperability claims | fix the RFC 8446 record-layer fault domain, add preserved OpenSSL 3.5+ peer evidence, keep stdlib fallback bounded |
| `R-TLS-TIER-MAPPING-DRIFT` | TLS peer program could be mistaken for a new evidence tier | high | `#15` | Wave 1A; claims registry | current certification evidence tiers | the TLS plan could drift into informal fourth-tier language, but the canonical certification tiers remain `local_conformance`, `same_stack_replay`, and `independent_certification` only | document that OpenSSL and curl peer evidence belongs under `independent_certification`, not a fourth tier |
| `R-TLS-ALPN-CONTRACT` | ALPN edge cases are under-specified for peer interop | medium | `#21` | Wave 1A; Wave 1 proxy/public policy closure | RFC 7301 | empty-string ALPN normalization mismatch can create local/peer behavior drift | freeze empty-input ALPN behavior and test it against peer expectations |
| `R-DEFAULT-BACKFILL-NONE` | Config defaults remain split across model, CLI, and normalize backfills | high | `#13`, `#17` | Wave 1 default and flag truth | operator-governance policy | `None` backfills and hidden normalization defaults create correctness and safety ambiguity | create the default audit artifact and reconcile reviewed defaults with tests and docs |
| `R-HTTP2-STATE-NONE` | HTTP/2 state uses incomplete defaults during protocol processing | high | `#18` | Wave 1 default and flag truth | RFC 9113 | protocol handlers compare against `None` instead of concrete limits/settings | restore invariant that protocol state is fully initialized before comparisons |
| `R-SFV-BASELINE-DRIFT` | Structured-fields work still references RFC 8941 semantics | medium | none | Wave 2A RFC 9651 targets | RFC 9651; IANA Structured Type metadata | docs and parser assumptions may drift from the current structured-fields baseline | replace active RFC 8941 references, add RFC 9651 conformance and peer checks |
| `R-FIELD-TERMINATION-DRIFT` | Package-owned field default behavior is not fully frozen | medium | none | Wave 2B HTTP fields and trace fields targets | RFC 9110; RFC 9112; RFC 9113; RFC 9114; RFC 6455; W3C Trace Context | field presence, suppression, pass-through, and termination behavior can drift across carriers and listener boundaries | build package-owned field inventory and certify default termination behavior |

## Review notes

- `R-TLS-8446-OPENSSL35` is the top current technical risk because it bears directly on the package-owned TCP/TLS claim.
- `R-TLS-TIER-MAPPING-DRIFT` is a governance risk created by shorthand tier language; it must be controlled in claim and evidence language.
- `R-DEFAULT-BACKFILL-NONE` and `R-HTTP2-STATE-NONE` are linked and likely share underlying initialization/defaulting causes.
- `R-SFV-BASELINE-DRIFT` and `R-FIELD-TERMINATION-DRIFT` are future in-bound risks, not current release blockers.
