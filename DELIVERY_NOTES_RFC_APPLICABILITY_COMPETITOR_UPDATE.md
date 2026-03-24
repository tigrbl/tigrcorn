# Delivery notes — RFC applicability / competitor update

This checkpoint tightens the RFC applicability answer for the user-shared HTTP integrity / caching / signatures table.

Changes in this update:

- aligned the broader `RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md` note with the focused `RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md` answer
- clarified that RFC 7232 and RFC 9530 are the most natural adjacent next targets after the current strict backlog
- clarified that RFC 9111 and RFC 9421 are conditional boundary-expansion work rather than automatic transport-server obligations
- refreshed the machine-readable snapshot and regression test accordingly

Repository truth remains unchanged:

- the authoritative release-gated RFC boundary is still green
- the stricter next-promotion target is still red
- the remaining strict blockers are still RFC 7692, RFC 9110 CONNECT / trailers / content coding, RFC 6960, several public flag/runtime gaps, and performance SLO closure
