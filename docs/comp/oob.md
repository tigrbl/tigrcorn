# Outside-boundary matrices

Reviewed on: `2026-03-28`

These tables list surfaces that are intentionally outside tigrcorn's current T/P/A/D/R product boundary.

Legend:

- `C-RFC` — tigrcorn implements the surface and includes it in the current certified RFC boundary.
- `C-OP` — tigrcorn implements the surface and includes it in the current certified public/operator surface.
- `S` — current official docs show first-class public support.
- `Cfg` — current official docs show public support through a primary config surface rather than a dedicated CLI switch.
- `P` — partial, optional, qualified, or draft support.
- `M` — middleware/wrapper based support instead of a first-class server surface.
- `O` — intentionally outside tigrcorn's current product boundary.
- `—` — no current official public support claim found in the reviewed primary docs.

## Outside-boundary RFC targets

| Surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| RFC 9218 Extensible Priorities | O | — | — | — | Outside the tigrcorn boundary; Hypercorn's docs mention HTTP/2 prioritisation but not RFC 9218. |
| RFC 9111 HTTP caching/freshness | O | — | — | — | Outside tigrcorn's direct origin/runtime boundary. |
| RFC 9530 Digest Fields | O | — | — | — | Outside tigrcorn's current boundary. |
| RFC 9421 HTTP Message Signatures | O | — | — | — | Outside tigrcorn's current boundary. |
| RFC 7515 / RFC 7516 / RFC 7519 JOSE stack | O | — | — | — | Non-core product layer for this repository. |
| RFC 8152 / RFC 9052 COSE stack | O | — | — | — | Non-core product layer for this repository. |

## Outside-boundary CLI feature families

| Surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| HTTP parser/backend selector | O | S | — | — | Uvicorn exposes `--http auto|h11|httptools`. |
| WebSocket engine selector | O | S | — | — | Uvicorn exposes `--ws ...`; tigrcorn intentionally does not. |
| Alternate interface selector (ASGI2/WSGI/RSGI) | O | S | S | S | tigrcorn stays ASGI3-only; peers expose broader interface selection. |
| Trio runtime / worker selection | O | — | S | — | Hypercorn documents trio workers; tigrcorn keeps Trio out of bounds. |
| Runtime topology / task-engine selector | O | — | — | S | Granian exposes runtime mode and task implementation knobs. |
| TLS protocol-min downgrade selector | O | S | — | S | Uvicorn exposes `--ssl-version`; Granian exposes `--ssl-protocol-min`; tigrcorn keeps downgrade policy out of bounds. |

## Outside-boundary public operator surfaces

| Surface | Tigrcorn | Uvicorn | Hypercorn | Granian | Notes |
|---|---|---|---|---|---|
| Parser pluggability as public product surface | O | S | — | — | Uvicorn publicly selects HTTP parsers; tigrcorn keeps parser pluggability out of bounds. |
| WebSocket engine pluggability | O | S | — | — | Uvicorn publicly selects WebSocket engines; tigrcorn keeps this out of bounds. |
| ASGI2 / WSGI / RSGI hosting families | O | S | S | S | tigrcorn stays ASGI3-only by policy. |
| Trio runtime family | O | — | S | — | Hypercorn documents trio workers; tigrcorn excludes Trio. |
| Runtime thread-topology / task-engine family | O | — | — | S | Granian exposes runtime mode and task implementation; tigrcorn excludes this family. |
| Gateway-style caching / integrity / signature behavior | O | — | — | — | tigrcorn keeps cache/integrity/signature gateways out of product scope. |

Boundary policy sources:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`
- `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md`
