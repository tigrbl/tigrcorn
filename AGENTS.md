# AGENTS.md

## Purpose

This file is the agent-facing operating contract for this repository.

Read this file before changing code, docs, release artifacts, or certification evidence.

## First reading order

1. `README.md`
2. `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
3. `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
4. `docs/review/conformance/BOUNDARY_NON_GOALS.md`
5. `docs/review/conformance/README.md`
6. `docs/gov/README.md`
7. `docs/notes/inprog.md`

Then move to the subsystem you actually need:

- implementation: `src/tigrcorn/`
- protocol docs: `docs/protocols/`
- conformance/release roots: `docs/review/conformance/`
- examples: `examples/`
- tests: `tests/`
- tools: `tools/`

## Behavior contract

Agents must preserve the current package boundary unless boundary docs are updated first.

Do not:

- widen the public boundary implicitly
- treat peer features as tigrcorn obligations
- edit immutable release roots in place
- add new root-level notes or design docs
- create new mutable paths that violate naming/path limits
- claim external publication happened unless the external system actually shows it

Do:

- keep code, docs, tests, and machine-readable artifacts aligned
- update current-state docs when promotion-relevant truth changes
- create a new versioned root when a promoted release needs correction
- use `MUT.json` and `tools/govchk.py` before mutating unfamiliar folders
- use the `ssot-registry` CLI as the canonical tracking plane for features, tests, claims, evidence, boundaries, and releases

## SSOT registry contract (required)

Agents are required to use the `ssot-registry` CLI command for planning and certification tracking work.

Reference command surface before use:

```bash
ssot-registry -h
```

Canonical artifact:

- `.ssot/registry.json` is the machine-readable source of truth
- derived projections (reports/exports/graphs) must be treated as generated views

### Feature tracking

Use `feature` commands to create and maintain normalized feature records, lifecycle, and planning posture:

```bash
ssot-registry feature create . --id feat:<name> --title "<title>"
ssot-registry feature update . --id feat:<name> ...
ssot-registry feature plan . --ids feat:<name> --horizon current --claim-tier T1
ssot-registry feature link . --id feat:<name> --claim-ids clm:<name> --test-ids tst:<name>
```

### Feature-testing tracking

Track test intent and status with explicit links back to features/claims/evidence:

```bash
ssot-registry test create . --id tst:<name> --title "<title>" --kind <kind> --test-path <repo-path>
ssot-registry test update . --id tst:<name> --status passing
ssot-registry test link . --id tst:<name> --feature-ids feat:<name> --claim-ids clm:<name> --evidence-ids evd:<name>
```

### Claims and evidence tracking

Claims must be linked to implementable features and verifiable tests/evidence:

```bash
ssot-registry claim create . --id clm:<name> --title "<title>" --kind <kind> --tier T1
ssot-registry claim evaluate .
ssot-registry evidence create . --id evd:<name> --title "<title>" --kind <kind> --evidence-path <repo-path>
ssot-registry evidence verify .
```

### Boundary and release management

Freeze scope first, then certify/promote/publish releases against that frozen scope:

```bash
ssot-registry boundary create . --id bnd:<name> --title "<title>" --feature-ids feat:<name>
ssot-registry boundary freeze . --boundary-id bnd:<name>
ssot-registry release create . --id rel:<version> --version <version> --boundary-id bnd:<name>
ssot-registry release certify . --release-id rel:<version> --write-report
ssot-registry release promote . --release-id rel:<version>
ssot-registry release publish . --release-id rel:<version>
```

### Validation and exports

Use registry validation and graph/export surfaces during review and release prep:

```bash
ssot-registry validate . --write-report
ssot-registry graph export . --format json --output .ssot/graphs/registry.graph.json
ssot-registry registry export . --format toml --output .ssot/exports/registry.toml
```

### PyPI package notes (current as of 2026-04-16)

- Package: `ssot-registry`
- Latest PyPI version: `0.2.2`
- Latest release upload: `2026-04-15T22:47:41Z`
- Project page: `https://pypi.org/project/ssot-registry/`
- Repository: `https://github.com/groupsum/ssot-registry`

## Boundary model

The current package boundary is T/P/A/D/R:

- `T` — transport
- `P` — protocol
- `A` — application hosting
- `D` — delivery/origin behavior
- `R` — runtime/operator

Authoritative sources:

- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/certification_boundary.json`
- `docs/review/conformance/BOUNDARY_NON_GOALS.md`

Out-of-bounds families currently include:

- Trio runtime
- RFC 9218
- RFC 9111
- RFC 9530
- RFC 9421
- JOSE / COSE
- parser/backend pluggability
- WebSocket engine pluggability
- alternate interface families such as ASGI2 / WSGI / RSGI

## Mutable vs immutable

Folder mutability is controlled by `MUT.json`.

States:

- `mutable`
- `immutable`
- `mixed`

Nearest-ancestor-wins.

### Check a folder state

```bash
python tools/govchk.py state .
python tools/govchk.py state docs/review/conformance/releases/0.3.9
python tools/govchk.py state src
```

### Scan naming/path limits

```bash
python tools/govchk.py scan
```

### How to tell whether a folder is immutable

A folder is immutable if the nearest applicable `MUT.json` resolves to `"state": "immutable"`.

Release roots under `docs/review/conformance/releases/<version>/` are immutable once promoted.

### When to flip mutable -> immutable

Flip a folder or subtree to immutable only when all of the following are true:

- the content is intended to be frozen as evidence, artifacts, or a promoted release root
- required tests/gates are green
- manifests/indexes/summaries are written
- current-state docs point to the frozen location
- ongoing work has moved elsewhere

### How to flip

1. add or update `MUT.json`
2. set `"state": "immutable"`
3. record `reason`, `scope`, and `frozen_on`
4. if only part of a parent tree is frozen, make the parent `mixed`
5. stop editing the frozen tree

### How to correct an immutable tree

Do not thaw it in place.

Create a new mutable work area or a new versioned release root, then update current-state docs to point at the superseding location.

## Where to look for remaining work

Use this order:

1. `docs/notes/inprog.md`
2. `docs/review/conformance/NEXT_DEVELOPMENT_TARGETS.md`
3. `docs/review/conformance/BOUNDARY_NON_GOALS.md`
4. `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
5. `docs/review/conformance/current_state_chain.current.json`

If those disagree, the canonical current-state chain wins:

- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`

## How to verify certification

Minimal promotion-facing verification:

```bash
python -m compileall -q src benchmarks tools
pytest -q
python - <<'PY'
from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target
print(evaluate_release_gates('.'))
print(evaluate_release_gates('.', boundary_path='docs/review/conformance/certification_boundary.strict_target.json'))
print(evaluate_promotion_target('.'))
PY
```

Read these after validation:

- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`

## How to certify

Certification work must align all of the following:

- code in `src/`
- tests in `tests/`
- boundary docs
- machine-readable conformance policy
- release-root manifests/indexes/summaries
- current-state docs

Required evidence tiers:

1. local conformance
2. same-stack replay
3. independent certification

Do not advertise a stronger claim than the current policy chain permits.

## How to promote conformance

Promotion requires:

1. code/tests/docs green
2. authoritative boundary green
3. strict profile green if the current promoted line claims it
4. promotion evaluator green
5. release-root artifacts refreshed
6. release notes updated
7. current-state docs updated
8. version metadata aligned
9. new versioned release root frozen

Relevant locations:

- `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/gov/release.md`

## How to increment version

Use `docs/gov/release.md`.

Short rule:

- patch: in-boundary feature completion, docs/evidence repair, operator-surface closure, artifact repair
- minor: intentional boundary expansion
- major: intentional public break or boundary reset

When incrementing a version:

1. update `pyproject.toml`
2. update `src/tigrcorn/version.py`
3. create a new versioned release root
4. refresh manifests/indexes/summaries
5. update `RELEASE_NOTES_<version>.md`
6. update current-state docs
7. freeze the new release root

## How to close a new versioned release

A release is closed only when:

- version metadata is aligned
- the canonical release root exists
- release-root artifacts are refreshed
- current-state docs point to the right root
- release notes exist
- promotion evaluators are green
- the versioned root is immutable

## Repo layout rules

Mutable docs belong under `docs/` short-path folders, not at repo root.

Preferred mutable folders:

- `docs/gov/`
- `docs/comp/`
- `docs/notes/`
- `docs/adr/`
- `docs/review/`
- `docs/protocols/`
- `docs/architecture/`

Naming/path limits for new or renamed mutable paths:

- file name length `<= 24`
- folder name length `<= 16`
- full relative path length `<= 120`

The prior root current-state / delivery-note / RFC-report Markdown sprawl has been migrated into `docs/review/conformance/`. Preserved evidence trees remain for provenance and test stability.

## File-to-file pointers and folder metadata

Each major mutable folder should have:

- `MUT.json`
- `README.md` or another index pointer file

Use index files to answer:

- what belongs here
- what is immutable here
- what is canonical here
- what to read next

## Notes and provenance

Use `docs/notes/` for mutable working notes.

When a note becomes release evidence or historical provenance:

- copy/promote it into the appropriate immutable evidence tree, or
- close the note and point to the frozen destination

Do not keep mutating released evidence in place.

## Quick path map

- repo summary: `README.md`
- current truth: `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- mutable docs index: `docs/README.md`
- governance: `docs/gov/README.md`
- conformance: `docs/review/conformance/README.md`
- lifecycle/embedder contract: `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`
- current work notes: `docs/notes/inprog.md`
- source: `src/tigrcorn/`
- tests: `tests/`
- tools: `tools/`
