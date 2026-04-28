# Authoring and maintainer guide

This guide explains how to update Tigrcorn's mutable repository surface without creating truth conflicts between code, tests, machine-readable artifacts, human documentation, and immutable release roots.

Current maintainer of record in package metadata: **Jacob Stewart** (`jacob@swarmauri.com`).

## Who this is for

- authors updating `README.md`, operator docs, or governance docs
- maintainers changing public CLI/API behavior
- release owners refreshing current-state or promotion materials
- agents/automation making repository edits

## Read order before making a documentation or public-surface change

1. `README.md`
2. `.codex/AGENTS.md`
3. `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
4. `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
5. `docs/review/conformance/BOUNDARY_NON_GOALS.md`
6. `docs/review/conformance/README.md`
7. the relevant folder guide:
   - `docs/ops/README.md`
   - `docs/gov/README.md`
   - `docs/protocols/`
   - `docs/comp/README.md`

## Truth hierarchy

When sources disagree, use this order:

1. **Definitive machine-readable truth**
   - `.ssot/registry.json`
   - `tools/ssot_sync.py`
   - normalized `.ssot` scaffold bootstrapped from `ssot-registry init`
2. **Canonical current-state truth**
   - `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
   - `docs/review/conformance/current_state_chain.current.json`
3. **Boundary and applicability policy**
   - `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
   - `docs/review/conformance/STRICT_PROFILE_TARGET.md`
   - `docs/review/conformance/BOUNDARY_NON_GOALS.md`
   - `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
4. **Machine-readable public surface truth**
   - `docs/review/conformance/cli_flag_surface.json`
   - `docs/review/conformance/deployment_profiles.json`
   - current JSON checkpoints under `docs/review/conformance/`
5. **Human operator/API docs**
   - `README.md`
   - `docs/ops/cli.md`
   - `docs/ops/public.md`
   - `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`
6. **Immutable release roots**
   - `docs/review/conformance/releases/0.3.9/release-0.3.9/`
   - older frozen roots under `docs/review/conformance/releases/`

Never “fix” a frozen release root in place. Supersede it with new mutable work and new current-state pointers.

## Where docs belong

Use short, purpose-scoped folders:

- `docs/ops/` — operator-facing CLI and programmatic/public-surface docs
- `docs/gov/` — governance, release, mutability, authoring workflow
- `docs/comp/` — comparison matrices and companion sources
- `docs/protocols/` — protocol-specific technical material
- `docs/architecture/` — system architecture docs
- `docs/adr/` — design decisions
- `docs/review/` — conformance, state, reports, delivery notes, release artifacts

Root remains intentionally narrow. Root documentation is limited to package entrypoints and community entrypoints such as:

- `README.md`
- `.codex/AGENTS.md`
- `RELEASE_NOTES_*.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`

## README contract

The root `README.md` is the package entrypoint for developers, operators, reviewers, and maintainers. Keep it aligned with the current repository truth.

It should continue to include:

- centered badge rows
- current release line and canonical promoted root pointers
- `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`
- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/phase9_implementation_plan.current.json`
- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- the external matrix JSON references:
  - `external_matrix.same_stack_replay.json`
  - `external_matrix.release.json`
  - `external_matrix.current_release.json`

Use footnotes for nuanced claim language rather than hiding qualifications in prose.
When a machine-readable statement exists in `.ssot/registry.json`, prose and derived JSON must conform to it rather than silently diverge.

## When to update which docs

### If you change canonical truth

Update `.ssot/registry.json` first, then regenerate or reconcile downstream docs and JSON views.
The `.ssot` directory scaffold itself is initialized by `tools/ssot_sync.py` through `ssot-registry init`.

### If you change CLI behavior

Update:

- `src/tigrcorn/cli.py`
- tests
- `docs/review/conformance/CLI_FLAG_SURFACE.md`
- `docs/review/conformance/cli_flag_surface.json`
- `docs/review/conformance/cli_help.current.txt`
- `docs/ops/cli.md`
- `README.md`
- current-state / promotion docs if the change affects release truth

### If you change public import surfaces

Update:

- `src/tigrcorn/__init__.py` and/or module `__all__` exports
- tests
- `docs/ops/public.md`
- `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` if lifecycle semantics changed
- `README.md`
- current-state docs if the operator surface or public claim changed

### If you change boundary or conformance truth

Update boundary docs first, then code/tests/docs. The README is downstream of boundary policy, not upstream of it.

### If you add or move mutable docs

Confirm path and naming rules in `docs/gov/tree.md`, add `MUT.json` where needed, and give the folder a pointer file such as `README.md`.

## Maintainer validation checklist

Run, at minimum:

```bash
python tools/ssot_sync.py --check
python tools/govchk.py scan
PYTHONPATH=src python -m compileall -q src benchmarks tools
PYTHONPATH=src pytest -q
```

Promotion-sensitive or boundary-sensitive work should also run:

```bash
PYTHONPATH=src python - <<'PY'
from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target

print(evaluate_release_gates('.').passed)
print(
    evaluate_release_gates(
        '.',
        boundary_path='docs/review/conformance/certification_boundary.strict_target.json',
    ).passed
)
print(evaluate_promotion_target('.').passed)
PY
```

## Mutability and frozen roots

Mutability is controlled by `MUT.json`.

Remember:

- nearest ancestor wins
- `mutable` means normal working area
- `immutable` means frozen evidence or release area
- `mixed` means the folder contains children with different states

Do not edit:

- `docs/review/conformance/releases/0.3.8/`
- `docs/review/conformance/releases/0.3.9/`

in place.

## Repo cleanliness reminders

- Keep root narrow.
- Prefer adding docs under `docs/ops/`, `docs/gov/`, or another scoped docs folder.
- Respect path limits for new or renamed mutable paths.
- Do not create a new root note when the material belongs in `docs/review/conformance/` or `docs/ops/`.
- If you are changing public claims, update code/tests/docs/current-state together.
