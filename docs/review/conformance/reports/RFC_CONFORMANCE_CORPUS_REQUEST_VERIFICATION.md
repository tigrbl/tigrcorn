# RFC conformance corpus request verification

Verification date: 2026-03-14

## Scope

This verification pass was executed against the supplied `tigrcorn_0.3.6_rfc_corpus_completed.zip` archive for the explicit task:

- expand the machine-readable conformance corpus so it enumerates RFC 9112, RFC 7541, RFC 9113, RFC 6455, RFC 7692, RFC 9114, RFC 9204, and the QUIC/TLS 1.3 subset intended for certification
- strengthen `tests/test_conformance_corpus.py` so it asserts coverage completeness rather than mere loadability

## Result

The supplied archive already satisfies that task.

### Confirmed corpus entries

`docs/review/conformance/corpus.json` enumerates the following RFC surfaces:

- RFC 9112
- RFC 7541
- RFC 9113
- RFC 6455
- RFC 7692
- RFC 8441
- RFC 8446 (QUIC-facing TLS 1.3 subset)
- RFC 9000
- RFC 9001
- RFC 9002
- RFC 9114
- RFC 9204
- RFC 9220

### Confirmed test hardening

`tests/test_conformance_corpus.py` now asserts:

- exact RFC catalog membership against an expected vector catalog
- uniqueness of RFCs, vector names, and fixtures
- that every fixture path exists
- that the local corpus covers the RFC surface documented in `docs/review/rfc_compliance_review.md`, plus additional claimed RFC 6455 / RFC 9000 / RFC 9001 surfaces

## Validation command

```text
pytest -q tests/test_conformance_corpus.py tests/test_documentation_reconciliation.py tests/test_tls13_engine_upgrade.py
```

Result: 15 passed

## Honest boundary

This verification confirms that the quoted corpus-completion task is done in this package.

It still does **not** make the package honestly certifiable as fully RFC compliant end to end, because preserved independent-peer HTTP/3 request/response and WebSocket-over-HTTP/3 evidence are still not bundled in the supplied materials.
