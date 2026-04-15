# ADR-1005: doc governance tree

# ADR 1005 — doc governance tree

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
- the previous root current-state / delivery-note / RFC-report docs are migrated into `docs/review/conformance/`, and new mutable docs stay out of root
