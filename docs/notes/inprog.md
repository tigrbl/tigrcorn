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

## Phase 5 follow-on

- generated origin/static truth now lives in `docs/conformance/origin_contract.json`, `docs/conformance/origin_contract.md`, `docs/conformance/origin_negatives.json`, `docs/conformance/origin_negatives.md`, and `docs/ops/origin.md`
- `src/tigrcorn/config/origin_surface.py` is now the canonical metadata source for the Phase 5 path-resolution, static-file-selection, HTTP-semantics, and `http.response.pathsend` contract
- `docs/review/conformance/flag_contracts.json` now carries the Phase 5 review overlay for the public static mount controls
- the runtime now rejects decoded parent-reference segments and Windows-style backslash separator segments in mounted static paths so origin traversal behavior stays platform-neutral
- `http.response.pathsend` now snapshots file length at dispatch, which freezes the growth-race contract even when later writes append bytes to the same path
- GitHub-side required-check enforcement for the Phase 5 parity tests still depends on the remote ruleset activation noted in the Phase 0 checkpoint

## Phase 6 follow-on

- generated observability truth now lives in `docs/conformance/metrics_schema.json`, `docs/conformance/metrics_schema.md`, `docs/conformance/qlog_experimental.json`, `docs/conformance/qlog_experimental.md`, and `docs/ops/observability.md`
- `src/tigrcorn/config/observability_surface.py` is now the canonical metadata source for the Phase 6 metric-family, exporter-adapter, and qlog experimental contract
- `docs/review/conformance/flag_contracts.json` now carries the Phase 6 review overlay for `--statsd-host` and `--otel-endpoint`
- StatsD/DogStatsD and OTEL exporter behavior is now versioned and generated as package-owned operator surface documentation instead of remaining implicit in the runtime modules
- qlog output is now explicitly marked experimental and redacted for endpoint and connection-id data in the package-owned observer generator
- GitHub-side required-check enforcement for the Phase 6 parity tests still depends on the remote ruleset activation noted in the Phase 0 checkpoint

## Phase 7 follow-on

- generated negative-certification truth now lives in `docs/conformance/fail_state_registry.json`, `docs/conformance/fail_state_registry.md`, `docs/conformance/negative_corpora.json`, `docs/conformance/negative_corpora.md`, `docs/conformance/negative_bundles.json`, `docs/conformance/negative_bundles.md`, and `docs/conformance/negative_bundles/`
- `src/tigrcorn/config/negative_surface.py` is now the canonical metadata source for fail-state actions, adversarial corpora, and expected-outcome bundle preservation
- fail-state behavior for proxy, early-data, QUIC, origin, CONNECT relay, TLS/X.509, and mixed-topology gate failures is now frozen as explicit package-owned registry rows instead of being inferred from scattered tests
- generated negative bundles now link current-tree expected outcomes to preserved historical release-root negative artifacts where those artifacts already exist
- local CI now regenerates the Phase 7 artifacts and runs `tests/test_phase7_negative_certification.py` as part of the canonical repository validation path
- GitHub-side required-check enforcement for the Phase 7 parity tests still depends on the remote ruleset activation noted in the Phase 0 checkpoint

## Phase 8 follow-on

- generated governance truth now lives in `docs/conformance/risk/RISK_REGISTER.json`, `docs/conformance/risk/RISK_TRACEABILITY.json`, `LEGACY_UNITTEST_INVENTORY.json`, `docs/conformance/sf9651.json`, `docs/conformance/interop_retention.json`, and `docs/conformance/perf_retention.json`
- `src/tigrcorn/config/governance_surface.py` is now the canonical metadata source for the release-gated risk graph, retained evidence inputs, stale structured-fields reference lint, and approved legacy unittest inventory
- `src/tigrcorn/http/structured_fields.py` is now the package-owned RFC 9651 helper surface for deterministic structured-field parsing and serialization used by the Phase 8 conformance bundle
- `src/tigrcorn/compat/release_gates.py` now fails closed when the governance graph is missing, when open blocking risk rows remain, or when new unittest-bearing files appear outside the approved legacy inventory
- `scripts/ci/validate.sh` now runs the canonical validation slice through `python -m pytest` so pytest is the only forward runner in CI even while legacy unittest files remain grandfathered
- GitHub-side required-check enforcement for the Phase 8 governance and RFC 9651 checks still depends on the remote ruleset activation noted in the Phase 0 checkpoint

## Phase 9 follow-on

- generated release-automation truth now lives in `docs/conformance/claim_rep.json`, `docs/conformance/risk_stat.json`, `docs/conformance/evidence_ix.json`, `docs/conformance/release_auto.json`, `docs/conformance/relnotes.json`, and `.artifacts/pages/`
- `tools/cert/release_auto.py` is now the canonical generator for release claim/risk/evidence summaries, generated release-note metadata, and the release-evidence Pages bundle
- `.github/workflows/publish-pypi.yml` now builds distributions once in `staging`, reuses the same artifact for TestPyPI and PyPI publishing through OIDC trusted publishing, attests the built distributions, attaches release evidence assets, and deploys the release-evidence Pages bundle
- `.github/workflows/docs.yml` now also regenerates and deploys the release-evidence Pages site for the mutable docs surface
- the mutable working tree now contains the automated release pipeline contract, but remote GitHub environment approval, trusted publisher registration on TestPyPI/PyPI, GitHub Pages activation, and observed successful tagged runs still remain external facts that must be verified on those systems before they can be claimed as completed publication
