# Risk register

Date: 2026-04-04

This is a mutable working risk register derived from the current issue register, issue matrix, feature matrix, TLS/OpenSSL peer plan, and the current certification-boundary evidence tiers.

This note does not widen the current package boundary. It is a working governance aid for selecting and sequencing future work.

## Active risks

| risk_id | title | severity | related issues | related targets | affected standards / policy | current concern | mitigation direction |
|---|---|---|---|---|---|---|---|
| `R-TLS-8446-OPENSSL35` | Custom TLS 1.3 fails strict external TCP/TLS peers | critical | `#15`, `#14` | Wave 1A TLS RFC and OpenSSL 3.5+ targets | RFC 8446; RFC 7301; RFC 5280; RFC 9525 | OpenSSL 3.5+ peers may reject the custom TLS record layer with `bad record type` and block honest external TCP/TLS interoperability claims | fix the RFC 8446 record-layer fault domain, add preserved OpenSSL 3.5+ peer evidence, keep stdlib fallback bounded |
| `R-TLS-8446-OUTER-FRAMING` | TLS protected record outer framing may be malformed | critical | `#15` | Atomic TLS row: RFC 8446 protected record outer framing | RFC 8446 | incorrect outer content type, legacy version encoding, or length accounting can produce immediate strict-peer `bad record type` or overflow failures | add byte-level record fixtures, malformed-length negatives, and OpenSSL 3.5+ read-path probes |
| `R-TLS-8446-INNER-TYPE` | TLS inner content type recovery may be encoded or parsed incorrectly | critical | `#15` | Atomic TLS row: RFC 8446 inner content type recovery | RFC 8446 | wrong `TLSInnerPlaintext.type` handling can make otherwise decryptable records unreadable to strict peers | add decrypt/reparse fixtures and wrong-inner-type negatives against strict peers |
| `R-TLS-8446-AAD` | AEAD additional data construction may diverge from peer expectations | critical | `#15` | Atomic TLS row: RFC 8446 AEAD additional data construction | RFC 8446 | header/AAD mismatch can cause opaque decrypt failures even when record framing looks correct | cross-check transcript construction against stdlib and OpenSSL behavior; add tamper corpus |
| `R-TLS-8446-PADDING` | TLS 1.3 padding handling may be ambiguous or non-compliant | high | `#15` | Atomic TLS row: RFC 8446 padding semantics | RFC 8446 | padding edge cases can break peer recovery of the inner content type or trigger close/fatal alerts | add padded-record interop probes and padding edge-case corpus |
| `R-TLS-8446-KEY-BOUNDARY` | Handshake/application-data key transition may be off by one record | critical | `#15` | Atomic TLS row: RFC 8446 handshake-to-application-data boundary | RFC 8446 | emitting the first encrypted application record under the wrong traffic keys can make handshakes appear complete while reads fail | assert transcript state transitions and first app-data record timing with `s_client` and curl |
| `R-TLS-TIER-MAPPING-DRIFT` | TLS peer program could be mistaken for a new evidence tier | high | `#15` | Wave 1A; claims registry | current certification evidence tiers | the TLS plan could drift into informal fourth-tier language, but the canonical certification tiers remain `local_conformance`, `same_stack_replay`, and `independent_certification` only | document that OpenSSL and curl peer evidence belongs under `independent_certification`, not a fourth tier |
| `R-TLS-ALPN-CONTRACT` | ALPN edge cases are under-specified for peer interop | medium | `#21` | Wave 1A; Wave 1 proxy/public policy closure | RFC 7301 | empty-string ALPN normalization mismatch can create local/peer behavior drift | freeze empty-input ALPN behavior and test it against peer expectations |
| `R-X509-CERT-PROFILE-DRIFT` | Demo and certification certificate profiles may fail modern verifier expectations | critical | `#15` | Atomic TLS rows: RFC 5280 AKI/SKI; KeyUsage/EKU; path validation | RFC 5280; RFC 9525 | weak or incomplete chain metadata can cause strict peers to fail even when the TLS record layer is repaired | require AKI/SKI, correct usages, SAN-based identity, and preserved OpenSSL path-validation evidence |
| `R-DEFAULT-BACKFILL-NONE` | Config defaults remain split across model, CLI, and normalize backfills | high | `#13`, `#17` | Wave 1 default and flag truth | operator-governance policy | `None` backfills and hidden normalization defaults create correctness and safety ambiguity | create the default audit artifact and reconcile reviewed defaults with tests and docs |
| `R-HTTP2-STATE-NONE` | HTTP/2 state uses incomplete defaults during protocol processing | high | `#18` | Wave 1 default and flag truth | RFC 9113 | protocol handlers compare against `None` instead of concrete limits/settings | restore invariant that protocol state is fully initialized before comparisons |
| `R-SFV-BASELINE-DRIFT` | Structured-fields work still references RFC 8941 semantics | medium | none | Wave 2A RFC 9651 targets | RFC 9651; IANA Structured Type metadata | docs and parser assumptions may drift from the current structured-fields baseline | replace active RFC 8941 references, add RFC 9651 conformance and peer checks |
| `R-FIELD-TERMINATION-DRIFT` | Package-owned field default behavior is not fully frozen | medium | none | Wave 2B HTTP fields and trace fields targets | RFC 9110; RFC 9112; RFC 9113; RFC 9114; RFC 6455; W3C Trace Context | field presence, suppression, pass-through, and termination behavior can drift across carriers and listener boundaries | build package-owned field inventory and certify default termination behavior |

## Review notes

- `R-TLS-8446-OPENSSL35` is the top current technical risk because it bears directly on the package-owned TCP/TLS claim.
- `R-TLS-8446-OUTER-FRAMING`, `R-TLS-8446-INNER-TYPE`, `R-TLS-8446-AAD`, `R-TLS-8446-PADDING`, and `R-TLS-8446-KEY-BOUNDARY` split the TLS fault domain into atomic execution and evidence rows so `#15` can be worked without umbrella ambiguity.
- `R-TLS-TIER-MAPPING-DRIFT` is a governance risk created by shorthand tier language; it must be controlled in claim and evidence language.
- `R-X509-CERT-PROFILE-DRIFT` stays mandatory even if the initial failure is record-layer specific, because strict peers will still reject weak AKI/SKI, KeyUsage, EKU, SAN, and path-validation posture.
- `R-DEFAULT-BACKFILL-NONE` and `R-HTTP2-STATE-NONE` are linked and likely share underlying initialization/defaulting causes.
- `R-SFV-BASELINE-DRIFT` and `R-FIELD-TERMINATION-DRIFT` are future in-bound risks, not current release blockers.
