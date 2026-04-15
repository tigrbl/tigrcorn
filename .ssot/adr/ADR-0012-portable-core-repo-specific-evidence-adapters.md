# ADR-0012: Portable core with repo-specific evidence generation outside the core

## Status
Accepted

## Decision
The core package validates and governs the registry graph, while repository-specific evidence generation remains external or adapter-driven.

## Consequences
- The package stays portable.
- Evidence generation does not hard-code repository-specific build logic.
