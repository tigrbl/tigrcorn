# Comparison notes

These matrices are the maintained comparison companion for `README.md`.

Reviewed on: `2026-03-28`

Scope rules:

- `tigrcorn` statuses are repository-internal and certification-aware.
- peer statuses are based on current official public docs only.
- peer statuses are **not** treated as certification claims in this repository.

Legend:

- `C-RFC` — tigrcorn implements the surface and includes it in the current certified RFC boundary.
- `C-OP` — tigrcorn implements the surface and includes it in the current certified public/operator surface.
- `S` — current official docs show first-class public support.
- `Cfg` — current official docs show public support through a primary config surface rather than a dedicated CLI switch.
- `P` — partial, optional, qualified, or draft support.
- `M` — middleware/wrapper based support instead of a first-class server surface.
- `O` — intentionally outside tigrcorn's current product boundary.
- `—` — no current official public support claim found in the reviewed primary docs.

Files:

- `rfc.md` — RFC target comparison
- `cli.md` — CLI feature comparison
- `ops.md` — public operator surface comparison
- `oob.md` — surfaces intentionally outside the current tigrcorn boundary
