# ADR-0007: Feature implementation state is separate from lifecycle state

## Status
Accepted

## Decision
`implementation_status` and `lifecycle.stage` are distinct fields.

## Consequences
- Deprecation, obsolescence, and removal are modeled cleanly.
- Implementation readiness is not overloaded with support-state semantics.
