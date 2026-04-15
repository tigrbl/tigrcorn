# ADR-0011: Explicit schema versioning

## Status
Accepted

## Decision
Breaking schema changes increment `schema_version` and require migration.

## Consequences
- No compatibility shims.
- No ambiguous reader behavior.
