# Mutability governance

## State model

Folder mutability is controlled by `MUT.json`.

States:

- `mutable` — normal working area; edits are expected
- `immutable` — frozen evidence or released artifacts; edits are prohibited
- `mixed` — container folder whose children may carry different states

## How to check a folder state

Use the nearest mutability marker:

```bash
python tools/govchk.py state docs/review/conformance/releases/0.3.9
python tools/govchk.py state src
```

The command prints the resolved state and the marker file that supplied it.

## Current intent by area

- `src/`, `tests/`, `tools/`, `examples/`, `benchmarks/` → mutable
- `docs/gov/`, `docs/comp/`, `docs/notes/`, `docs/adr/`, `docs/architecture/`, `docs/protocols/` → mutable
- `docs/review/` → mixed
- `docs/review/conformance/` → mixed
- `docs/review/conformance/releases/0.3.8/` → immutable
- `docs/review/conformance/releases/0.3.9/` → immutable
- repository root → mixed

## How to mark a folder immutable

A folder may be flipped from `mutable` to `immutable` only when all of the following are true:

- the folder content is intended to be frozen for provenance, release, or certification
- required tests/gates for that folder are green
- required manifests/indexes/summaries are written
- the parent/current-state docs point at the frozen location
- the responsible release/governance doc records the freeze

Then:

1. update or add `MUT.json`
2. set `"state": "immutable"`
3. record `reason`, `frozen_on`, and `scope`
4. ensure no mutable work continues in that folder
5. if only part of a tree is frozen, mark the parent `mixed`

## How to flip a folder back to mutable

Do not thaw immutable release/evidence folders in place.

If correction is required:

- create a new mutable work area or new versioned release root
- leave the old folder immutable
- record the superseding path in current-state docs

## Release-root rule

Versioned release roots are immutable after promotion.

Corrections after promotion create a new versioned root; they do not rewrite a frozen historical root.

## Mutable-note rule

`docs/notes/` remains mutable. Once a note becomes release evidence or historical provenance, copy or promote it into an immutable evidence tree and then stop editing the original note or mark it as closed.
