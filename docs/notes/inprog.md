# In-progress and remaining work

## Current line

- canonical repository target: `0.3.9`
- canonical release root: `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- authoritative boundary: green
- strict target: green
- promotion target: green

## In-bounds remaining work

There are no open in-bounds certification blockers for the current `0.3.9` line.

## Current operational follow-on

- GitHub control-plane scaffolding now exists locally under `.github/`, `scripts/ci/`, `tools/cert/`, `docs/governance/`, and `docs/conformance/`
- remote GitHub activation still remains to be completed for rulesets, protected environments, Dependabot alerts, CodeQL policy, and artifact-attestation enforcement
- current package conformance claims remain green locally after the Phase 0 hardening pass

Future work must start by deciding whether it is:

- in-bounds maintenance
- a patch-level operator/docs/evidence improvement
- a boundary expansion that requires a minor-version decision

## Explicitly out of scope for the current line

See:

- `docs/review/conformance/BOUNDARY_NON_GOALS.md`
- `docs/comp/oob.md`

## Documentation/layout follow-on

The new short-path governance tree is now in place. The previous root current-state / delivery-note / RFC-report Markdown files have been migrated into `docs/review/conformance/`, while legacy conformance artifact filenames remain grandfathered where needed for preserved evidence trees.

## Phase 1 follow-on

- the blessed Phase 1 deployment profiles are now generated from `src/tigrcorn/config/profiles.py`
- the mutable runtime/profile/operator truth now lives in `profiles/`, `docs/ops/profiles.md`, and `docs/conformance/profile_bundles.json`
- future profile work should extend the same registry instead of reintroducing normalize-time posture ambiguity
