# Release governance

## Versioning rules

Use semantic intent, anchored to the frozen package boundary.

### Patch release (`0.3.x` -> `0.3.x+1`)

Use a patch release for:

- in-boundary feature completion
- cert/evidence closure
- release-artifact repair
- docs/governance truth corrections
- operator-surface completion that does not widen the current product boundary

Example: `0.3.8 -> 0.3.9`

### Minor release (`0.3.x` -> `0.4.0`)

Use a minor release when the public boundary expands, for example:

- new supported runtime family
- new app-interface family
- new RFC family added to the required boundary
- new product-layer capability intentionally adopted into T/P/A/D/R

### Major release

Use a major release only for an intentional public break or a boundary reset.

## Certification tiers

Evidence tiers:

1. `local_conformance`
2. `same_stack_replay`
3. `independent_certification`

Promotion status is not a fourth evidence tier; it is the result of the release-gate and promotion evaluators.

## Promotion flow

1. finish code/docs/tests
2. refresh `.ssot/registry.json`
3. refresh current-state docs
4. run compileall
5. run targeted/full pytest as needed
6. run `evaluate_release_gates('.')`
7. run strict target if applicable
8. run `evaluate_promotion_target('.')`
9. refresh release-root `manifest.json`, `bundle_index.json`, `bundle_summary.json`
10. update `RELEASE_NOTES_*.md`
11. update versioned release root
12. freeze the new versioned root with `MUT.json`
13. leave old promoted roots immutable

## Closing a release

A release is closed only when:

- version metadata is aligned
- `.ssot/registry.json` is aligned with the promoted state
- the canonical release root exists
- the current-state chain points to the right root
- release notes are updated
- promotion evaluators are green
- the versioned root is immutable

## Publishing note

The mutable tree now carries an automated release pipeline that builds distributions once, promotes the same artifacts through TestPyPI and PyPI via OIDC trusted publishing, attaches generated release evidence, and deploys a release-evidence Pages bundle.

External publication and deployment are still operator-observed facts rather than repository-local assumptions. Repository promotion must not claim that TestPyPI, PyPI, GitHub Releases, artifact attestations, or GitHub Pages publication actually happened until those external systems show the successful run and published outputs.
