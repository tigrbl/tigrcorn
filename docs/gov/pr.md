# PR governance

## Required PR sections

Every PR should include:

- scope
- boundary impact
- mutability impact
- validation run
- docs updated
- version impact
- release impact

## Review rules

- boundary-expanding work needs an ADR plus updates to `CERTIFICATION_BOUNDARY.md` and `BOUNDARY_NON_GOALS.md`
- release-root promotions require refreshed manifests, bundle indexes, bundle summaries, release notes, and current-state docs
- immutable folder changes must be rejected unless the PR is creating a new versioned immutable root
- new mutable docs must follow the path and name limits from `docs/gov/tree.md`

## Validation expectations

At minimum, promotion-relevant PRs should run:

- `python -m compileall -q src benchmarks tools`
- the relevant pytest slice
- `evaluate_release_gates('.')`
- strict target, if affected
- `evaluate_promotion_target('.')`, if affected
