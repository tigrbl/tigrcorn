# ADR-0009: Fail-closed guards

## Status
Accepted

## Decision
Validation, certification, promotion, publication, and lifecycle transitions refuse to proceed on guard violations.

## Consequences
- No silent drift.
- No optimistic release progression.
