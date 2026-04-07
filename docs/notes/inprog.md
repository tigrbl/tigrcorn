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

## Phase 2 follow-on

- generated default-audit truth now lives in `DEFAULT_AUDIT.json`, `DEFAULT_AUDIT.md`, `PROFILE_DEFAULTS/`, and `docs/ops/defaults.md`
- `src/tigrcorn/config/audit.py` is now the canonical resolver for dataclass defaults, parser defaults, normalization backfills, and profile overlays
- `docs/review/conformance/flag_contracts.json` is now Phase 2 reviewed and machine-readable for all current public flag rows
- GitHub-side required-check enforcement for the Phase 2 default parity tests still depends on the remote ruleset activation noted in the Phase 0 checkpoint

## Phase 3 follow-on

- generated proxy and policy truth now lives in `docs/conformance/proxy_contract.json`, `docs/conformance/proxy_contract.md`, `docs/conformance/policy_surface.json`, `docs/ops/policies.md`, and `docs/review/conformance/cli_help.current.txt`
- `src/tigrcorn/config/policy_surface.py` is now the canonical metadata source for the Phase 3 proxy contract, policy groups, and synchronized CLI help text
- `docs/review/conformance/flag_contracts.json` now carries the Phase 3 review overlay for the promoted public policy controls
- future work on proxy semantics or operator-policy flags should extend the shared policy metadata and regeneration path instead of reintroducing hidden runtime-only behavior
- GitHub-side required-check enforcement for the Phase 3 parity tests still depends on the remote ruleset activation noted in the Phase 0 checkpoint

## Phase 4 follow-on

- generated QUIC semantic truth now lives in `docs/conformance/early_data_contract.json`, `docs/conformance/early_data_contract.md`, `docs/conformance/quic_state.json`, and `docs/conformance/quic_state.md`
- `src/tigrcorn/config/quic_surface.py` is now the canonical metadata source for the Phase 4 early-data, replay, topology, and QUIC state-claim surface
- `docs/review/conformance/flag_contracts.json` now carries the Phase 4 review overlay for `--quic-early-data-policy` and the Retry-facing QUIC contract rows
- future work on QUIC topology or 0-RTT behavior should extend the shared Phase 4 metadata and preserved evidence mapping instead of reintroducing vague HTTP/3 support language
- GitHub-side required-check enforcement for the Phase 4 parity tests still depends on the remote ruleset activation noted in the Phase 0 checkpoint
