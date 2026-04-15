# ADR-1006: mutable and immutable marks

# ADR 1006 — mutable and immutable marks

## Status

Accepted

## Context

The repository needs an explicit rule for frozen release/evidence folders and an agent-friendly way to resolve whether a path may be edited.

## Decision

Use `MUT.json` as the canonical folder-state marker.

States:

- `mutable`
- `immutable`
- `mixed`

Nearest-ancestor-wins.

## Consequences

- promoted release roots are immutable
- preserved historical roots stay immutable
- parents of mixed frozen/mutable trees are marked `mixed`
- agents can query folder state with `python tools/govchk.py state PATH`
