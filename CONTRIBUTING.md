# Contributing

Thanks for contributing to Tigrcorn.

This repository is not organized as a loose collection of notes and code. It has a documented certification boundary, a documented public/operator surface, current-state records, immutable release roots, and machine-readable truth files that must stay aligned. Contributions are welcome, but they need to preserve that discipline.

## Read this first

1. `README.md`
2. `AGENTS.md`
3. `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
4. `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
5. `docs/review/conformance/BOUNDARY_NON_GOALS.md`
6. `docs/gov/authoring.md`

If your work is operator-facing, also read:

- `docs/ops/cli.md`
- `docs/ops/public.md`
- `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`

## What kinds of changes are welcome

- bug fixes inside the current product boundary
- documentation improvements that make the current state easier to understand
- test hardening and validation improvements
- operator-surface improvements that stay inside the documented public surface
- release/provenance improvements that keep current-state and frozen roots honest

If you want to widen the public boundary, do not start by editing the README alone. Update boundary policy and current-state docs first.

## Boundary and mutability rules

- The authoritative RFC claim is defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.
- Explicit non-goals live in `docs/review/conformance/BOUNDARY_NON_GOALS.md`.
- Frozen release roots under `docs/review/conformance/releases/` are immutable.
- Mutability is governed by `MUT.json` and documented in `docs/gov/mut.md`.
- New mutable docs should live under `docs/`, not as new root notes.

## If you change code, update the matching docs and truth files

### CLI changes

Update all of these together:

- code
- tests
- `docs/review/conformance/CLI_FLAG_SURFACE.md`
- `docs/review/conformance/cli_flag_surface.json`
- `docs/review/conformance/cli_help.current.txt`
- `docs/ops/cli.md`
- `README.md`
- current-state / promotion docs if the change affects release truth

### Public import surface changes

Update all of these together:

- code
- tests
- `docs/ops/public.md`
- `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md` if lifecycle semantics changed
- `README.md`
- current-state docs if the public claim changed

### Current-state or promotion truth changes

Update the canonical conformance docs first, then the README and secondary docs.

## Validation checklist

Run at minimum:

```bash
python tools/govchk.py scan
PYTHONPATH=src python -m compileall -q src benchmarks tools
PYTHONPATH=src pytest -q
```

Promotion-sensitive work should also run:

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

## Pull request checklist

Before opening or merging a PR, confirm:

- the change respects the documented boundary
- immutable release roots were not edited in place
- docs, tests, and machine-readable truth files were updated together
- the root stays clean
- any new docs were placed in the right `docs/` subtree
- `README.md` still points to the canonical current-state and boundary docs
- validation commands were run at an appropriate depth for the change

## Community expectations

Participation is governed by `CODE_OF_CONDUCT.md`.

Be direct, specific, and evidence-based. If you are changing a claim, point to the source file or artifact that makes the claim true.
