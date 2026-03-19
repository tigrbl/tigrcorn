# RFC conformance corpus completion update

This update completes the quoted certifying-corpus task for the supplied source archive.

## What changed

- `docs/review/conformance/corpus.json` now explicitly includes the QUIC-facing RFC 8446 TLS 1.3 subset through `tests/test_tls13_engine_upgrade.py` in addition to the existing RFC 9001 QUIC-TLS vectors.
- `tests/test_conformance_corpus.py` now validates the full expected RFC vector catalog, checks uniqueness, verifies fixture existence, and ensures the local corpus covers the RFC surface documented in `docs/review/rfc_compliance_review.md` plus the additional claimed RFC 6455 / RFC 9000 / RFC 9001 surfaces.
- `README.md` and `docs/review/conformance/README.md` now state the completed local corpus boundary precisely.

## Honest boundary

This change completes the local certifying-corpus gap described in the quoted review text.

It does **not** remove the remaining package-level certification blocker: preserved independent-peer HTTP/3 request/response and WebSocket-over-HTTP/3 evidence is still not bundled in the supplied materials.
