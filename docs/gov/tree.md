# Tree governance

## Purpose

This document defines the sustainable project layout for the mutable repository surface.

## Root contract

The repository root is intentionally narrow.

Mutable root files are limited to:

- `README.md`
- `AGENTS.md`
- `CURRENT_REPOSITORY_STATE.md`
- `RELEASE_NOTES_*.md`
- build/config roots such as `pyproject.toml`, `Makefile`, `.gitignore`, `LICENSE`

New operational, design, governance, or progress notes must **not** be added to root. New documentation belongs under `docs/`.

Historical root notes that already exist are grandfathered as legacy archival files. They are treated as immutable compatibility artifacts unless a dedicated migration ADR moves them.

## Mutable documentation layout

New mutable docs land in short, purpose-scoped folders:

- `docs/gov/` — governance
- `docs/comp/` — comparison matrices
- `docs/notes/` — mutable notes and current work tracking
- `docs/adr/` — architecture decisions
- `docs/review/` — review and conformance material
- `docs/protocols/` — protocol-specific technical docs
- `docs/architecture/` — architecture explanations

Each mutable folder should carry:

- `MUT.json` — folder mutability metadata
- a pointer/index file such as `README.md` or `IDX.md`

## Naming rules

These limits are mandatory for **new or renamed mutable paths** from this checkpoint onward:

- file name length: `<= 24`
- folder name length: `<= 16`
- full relative path length: `<= 120`

Use abbreviations only when they remain obvious, searchable, and stable.

## Grandfathered legacy exceptions

Pre-existing legacy paths are grandfathered until they are explicitly migrated. This includes:

- preserved root archival notes
- preserved release/conformance artifact trees
- pre-existing ADR names
- pre-existing example paths
- pre-existing test/tool paths
- pre-existing performance-artifact paths
- other legacy mutable support files explicitly listed in the root `MUT.json`

Grandfathered paths are not a license to create new violations.

## Pointer rules

Every major mutable folder must have a human pointer file that answers:

- what belongs here
- what is immutable here
- where the canonical current-state source is
- what the next folder to read is

## Folder metadata rules

`MUT.json` is the canonical folder-state marker.

Nearest-ancestor-wins:

1. look for `MUT.json` in the target folder
2. if absent, walk upward
3. the first marker found defines the folder state

Allowed states:

- `mutable`
- `immutable`
- `mixed`

## Recommended top-level reading order

1. `README.md`
2. `AGENTS.md`
3. `CURRENT_REPOSITORY_STATE.md`
4. `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
5. `docs/review/conformance/BOUNDARY_NON_GOALS.md`
6. `docs/review/conformance/README.md`
7. the relevant folder `README.md` / `IDX.md`

## Enforcement

Run:

- `python tools/govchk.py state PATH`
- `python tools/govchk.py scan`

before closing a documentation/layout change.
