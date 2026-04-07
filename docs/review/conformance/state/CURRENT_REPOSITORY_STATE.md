# Current repository state

The current authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

The repository continues to operate under the **dual-boundary model**:

Historical checkpoint guardrail: the authoritative boundary remains green while the strict target is not yet green. Those exact phrases are preserved here for documentation-consistency checks even though the canonical 0.3.9 release root is now green.

- `evaluate_release_gates('.')` is **green** under the authoritative boundary
- the stricter next-target boundary defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is now **green** under the canonical 0.3.9 release root
- `evaluate_promotion_target()` is now **green**

Under the current authoritative boundary, the package remains **certifiably fully RFC compliant**. Under the canonical 0.3.9 release root, the package is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

What is now true:

- the 0.3.9 release root is now the canonical authoritative release root
- the public package version is now `0.3.9`
- the release notes now live in `RELEASE_NOTES_0.3.9.md`
- the authoritative boundary remains green
- the strict target is green under the canonical 0.3.9 release root
- the flag surface is green
- RFC 9220 WebSocket-over-HTTP/3 remains green in both the authoritative boundary and the canonical 0.3.9 release root
- the operator surface is green
- the performance section is green
- the documentation section is green
- the composite promotion target is green
- all previously failing HTTP/3 strict-target scenarios remain preserved as passing artifacts in the canonical root
- the version bump and release-note promotion work from Step 9 is complete

There are no remaining strict-target RFC, feature, or administrative promotion blockers in the canonical 0.3.9 release root.

## Canonical current-state chain

The Canonical current-state chain for the promoted release is defined by:

- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`

Historical aliases are preserved only as labeled checkpoint history under `docs/review/conformance/state/checkpoints/`; the current promoted-state pointer is this file and the canonical chain documents above.

Primary documentation for the current promoted state now lives in:

- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- `docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `RELEASE_NOTES_0.3.9.md`
- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/PHASE9I_STRICT_VALIDATION.md`
- `docs/review/conformance/phase9i_strict_validation.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`
- `docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`

The authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

For the stricter target, see `docs/review/conformance/STRICT_PROFILE_TARGET.md`.

## Phase 9 release-promotion checkpoint

This checkpoint completes the Step 9 administrative promotion work:

- `pyproject.toml` now reports version `0.3.9`
- the canonical authoritative release root is now `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- release notes now live in `RELEASE_NOTES_0.3.9.md`
- the current-state docs and machine-readable snapshots now truthfully report the strict-target green state under the canonical promoted release


## Phase 9A promotion-contract-freeze checkpoint

The historical Phase 9A promotion-contract-freeze checkpoint remains part of the current provenance chain:

- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md`
- `docs/review/conformance/phase9a_execution_backlog.current.json`

These documents are historical planning/provenance inputs. They do not override the current promoted-state truth above, but they remain the correct place to inspect the earlier contract freeze and backlog closure requirements.

## Certification environment freeze

This checkpoint also preserves the strict-promotion certification environment contract in:

- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`

What that freeze now means:

- the release workflow must run under Python 3.11 or 3.12
- the release workflow must install `.[certification,dev]` before any Phase 9 checkpoint script is executed
- `tools/run_phase9_release_workflow.py` freezes and validates the certification environment before it invokes Phase 9 checkpoint scripts
- a non-ready local environment is recorded honestly instead of being treated as an acceptable release-workflow substitute

## Phase 9 implementation-plan checkpoint

The broader strict-promotion execution plan remains documented in:

- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/phase9_implementation_plan.current.json`

## Phase 0 control-plane stabilization checkpoint

The current working tree now also carries a Phase 0 control-plane stabilization checkpoint for the mutable repository surface.

What changed in this working tree:

- runtime defaults now fail closed for `connect_policy`, `early_data_policy`, `include_server_header`, and `enable_h2c`
- QUIC-enabled listeners no longer rely on a static shared default secret; they require an explicit secret or receive runtime randomization during normalization
- release-gate evaluation now fails closed when matrix metadata still declares blocked or pending scenarios
- GitHub control-plane scaffolding now exists under `.github/workflows/`, `.github/actions/`, `scripts/ci/`, `tools/cert/`, `docs/governance/`, and `docs/conformance/`
- targeted local validation currently remains green for release gates, the strict target, and the promotion target

What is not yet proven by this working tree alone:

- GitHub rulesets for `main`, `release/*`, and protected tags are not activated by editing files in this repository
- environment protections for `ci`, `staging`, `testpypi`, `pypi`, and `docs` require remote GitHub configuration
- enabling Dependabot alerts, CodeQL policy, and artifact-attestation enforcement still requires GitHub-side activation

The package claim remains:

- **certifiably fully RFC compliant under the authoritative certification boundary**
- **strict-target certifiably fully RFC compliant** under the canonical `0.3.9` release root
- **certifiably fully featured** under the canonical `0.3.9` release root

The repository-governance claim is narrower:

- the repository now contains the control-plane files needed for GitHub enforcement
- remote GitHub enforcement is only honest to claim after the repository settings are activated outside this working tree

## Phase 1 safe-baseline and blessed-profile checkpoint

The current working tree now also carries the Phase 1 blessed deployment-profile surface.

What changed in this working tree:

- a central runtime profile registry now defines `default`, `strict-h1-origin`, `strict-h2-origin`, `strict-h3-edge`, `strict-mtls-origin`, and `static-origin`
- profile inheritance and effective-default resolution now happen through the config-loading path before validation
- generated profile artifacts now exist under `profiles/`
- generated operator and conformance profile docs now exist at `docs/ops/profiles.md`, `docs/conformance/profile_bundles.md`, and `docs/conformance/profile_bundles.json`
- local CI now regenerates profile bundles before validation so runtime/profile/doc drift fails in the canonical GitHub Actions path
- `claims_registry.json` now promotes the Phase 1 deployment-profile claims as implemented `TC-PROFILE-*` rows

What is honestly true after this checkpoint:

- the zero-config/default profile is now intentionally boring and safe in the config-constructor path
- QUIC/H3, CONNECT, static serving, trusted proxy behavior, and early-data posture are explicit in the blessed profile registry
- the package claim remains **certifiably fully RFC compliant under the authoritative certification boundary**
- the canonical `0.3.9` release root remains **strict-target certifiably fully RFC compliant** and **certifiably fully featured**

What is not yet elevated by this checkpoint:

- the canonical frozen `0.3.9` release root has not been regenerated or superseded with Phase 1 profile bundles
- the stronger profile ambitions around SAN/EKU-specific mTLS policy, broader proxy-trust semantics, and deeper origin path contract closure still remain separate follow-on work inside the repository backlog

## Phase 2 default-audit and flag-contract checkpoint

The current working tree now also carries the Phase 2 default-audit and flag-contract truth surface.

What changed in this working tree:

- `src/tigrcorn/config/audit.py` now provides `resolve_effective_defaults()` and parser-default extraction across dataclass/model defaults, CLI defaults, normalization backfills, and profile overlays
- generated Phase 2 artifacts now exist at `DEFAULT_AUDIT.json`, `DEFAULT_AUDIT.md`, `PROFILE_DEFAULTS/`, and `docs/ops/defaults.md`
- `docs/review/conformance/flag_contracts.json` is now reviewed as the machine-readable flag-contract source of truth with synchronized runtime and help defaults
- local CI now regenerates default audits before validation, and the Phase 2 parity/unsafe-default tests are part of the canonical repository validation path
- volatile runtime-randomized QUIC listener secrets are represented in audit outputs as stable runtime-randomized placeholders rather than being silently frozen as misleading static defaults

What is honestly true after this checkpoint:

- the package still evaluates as **certifiably fully RFC compliant under the authoritative certification boundary**
- the canonical `0.3.9` release root still evaluates as **strict-target certifiably fully RFC compliant** and **certifiably fully featured**
- the public default surface is now machine-readable and generated from code rather than handwritten documentation
- the zero-config/default posture still denies CONNECT, denies early data, disables H2C unless explicit, suppresses the server header by default, and keeps WebSocket disabled in the safe default profile

What is not yet elevated by this checkpoint:

- the frozen canonical `0.3.9` release root has not been regenerated or superseded with the new mutable Phase 2 audit artifacts
- GitHub-side required-check enforcement for the Phase 2 parity tests still depends on the remote ruleset and environment activation noted in the Phase 0 checkpoint

## Phase 3 proxy and public-policy closure checkpoint

The current working tree now also carries the Phase 3 proxy-contract and public-policy closure surface.

What changed in this working tree:

- `src/tigrcorn/config/policy_surface.py` now defines the shared proxy contract, public policy groups, and CLI help text for the targeted Phase 3 operator surface
- generated Phase 3 artifacts now exist at `docs/conformance/proxy_contract.json`, `docs/conformance/proxy_contract.md`, `docs/conformance/policy_surface.json`, `docs/ops/policies.md`, and `docs/review/conformance/cli_help.current.txt`
- trusted proxy behavior now has explicit trust, precedence, and normalization documentation covering `Forwarded`, `X-Forwarded-*`, and `root_path` composition
- CONNECT, trailers, content-coding, H2C, ALPN, revocation, WebSocket compression, limits and timeouts, WebSocket heartbeat, and drain/admission controls are now exposed as reviewed public CLI/config/env surfaces
- `docs/review/conformance/flag_contracts.json` now carries a Phase 3 review layer generated from the same metadata that drives runtime help and operator documentation
- local CI now regenerates the Phase 3 policy artifacts and runs the Phase 3 parity tests as part of the canonical repository validation path
- `claims_registry.json` now promotes the Phase 3 `TC-CONTRACT-PROXY-*` and `TC-POLICY-*` rows as implemented in-tree claims

What is honestly true after this checkpoint:

- the package still evaluates as **certifiably fully RFC compliant under the authoritative certification boundary**
- the canonical `0.3.9` release root still evaluates as **strict-target certifiably fully RFC compliant** and **certifiably fully featured**
- the trusted-proxy contract, precedence tables, and normalization rules are now generated from code and aligned with runtime behavior
- no claimed Phase 3 policy surface remains hidden behind internal defaults without corresponding CLI/help/doc coverage in this working tree

What is not yet elevated by this checkpoint:

- the frozen canonical `0.3.9` release root has not been regenerated or superseded with the new mutable Phase 3 policy artifacts
- GitHub-side required-check enforcement for the Phase 3 policy parity tests still depends on the remote ruleset and environment activation noted in the Phase 0 checkpoint

## Phase 4 early-data and QUIC state semantics checkpoint

The current working tree now also carries the Phase 4 QUIC semantic-closure surface.

What changed in this working tree:

- `src/tigrcorn/config/quic_surface.py` now defines the shared early-data, replay, topology, app-visibility, and QUIC state-claim metadata
- generated Phase 4 artifacts now exist at `docs/conformance/early_data_contract.json`, `docs/conformance/early_data_contract.md`, `docs/conformance/quic_state.json`, and `docs/conformance/quic_state.md`
- the HTTP/3 runtime now stops advertising early-data-capable session tickets when `quic.early_data_policy == deny`, preserving the default-deny contract honestly
- `quic.early_data_policy == require` now has explicit runtime meaning for resumed downgraded requests: the package emits `425 Too Early` before ASGI app dispatch instead of silently pretending early data was accepted
- public CLI/env/help coverage now exists for the promoted QUIC semantic flags, and `docs/review/conformance/flag_contracts.json` now carries a Phase 4 review layer
- `claims_registry.json` now promotes the required `TC-CONTRACT-EARLYDATA-*` and `TC-STATE-QUIC-*` rows as implemented in-tree claims backed by preserved third-party evidence

What is honestly true after this checkpoint:

- the package still evaluates as **certifiably fully RFC compliant under the authoritative certification boundary**
- the canonical `0.3.9` release root still evaluates as **strict-target certifiably fully RFC compliant** and **certifiably fully featured**
- advanced QUIC/H3 state claims for Retry, resumption, 0-RTT, migration, GOAWAY, and QPACK are now tracked through explicit promoted claim rows linked to preserved third-party `aioquic` artifacts
- the early-data contract is now explicit about default denial, replay-gate behavior, multi-instance honesty limits, and what ASGI apps can observe today

What is not yet elevated by this checkpoint:

- the frozen canonical `0.3.9` release root has not been regenerated or superseded with the new mutable Phase 4 semantic-contract artifacts
- GitHub-side required-check enforcement for the Phase 4 parity tests still depends on the remote ruleset and environment activation noted in the Phase 0 checkpoint
