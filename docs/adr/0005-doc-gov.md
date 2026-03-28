# ADR 0005 — doc governance tree

## Status

Accepted

## Context

The repository needs a durable, scalable documentation layout that keeps new mutable docs out of root and makes navigation obvious for both humans and agents.

## Decision

Adopt short-path mutable documentation folders under `docs/`:

- `docs/gov/`
- `docs/comp/`
- `docs/notes/`

Use `MUT.json` markers plus index files for navigation.

## Consequences

- new mutable docs must land under `docs/`
- root receives no new operational notes
- legacy root docs remain grandfathered until a dedicated migration
