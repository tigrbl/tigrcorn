# ADR-0001: Canonical registry is a single JSON document

## Status
Accepted

## Decision
The only authored machine-readable source of truth is `.ssot/registry.json`.

## Consequences
- Split manifests, spreadsheets, and parallel mapping files are non-canonical.
- Reports, graphs, CSV projections, Markdown summaries, and SQLite mirrors are generated.
