# Current repository state

Repository target note: the repository line is promoted as canonical `0.3.9`, and the originally released `0.3.8` conformance tree remains preserved unchanged at `docs/review/conformance/releases/0.3.8/release-0.3.8/`.

The current authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.


The repository continues to operate under the **dual-boundary model**:

- the authoritative current package boundary is `docs/review/conformance/CERTIFICATION_BOUNDARY.md`
- the preserved stricter satisfied profile is `docs/review/conformance/STRICT_PROFILE_TARGET.md`

Historical checkpoint guardrail: the authoritative boundary remains green while the strict target is not yet green. That sentence is preserved here as a historical compatibility phrase for older checkpoint references; it is not the current release truth for the promoted `0.3.9` line.


## Current truth

- `evaluate_release_gates('.')` is **green** under the authoritative boundary
- `evaluate_release_gates('.', boundary_path='docs/review/conformance/certification_boundary.strict_target.json')` is **green**
- `evaluate_promotion_target('.')` is **green**

Under the authoritative boundary, the package remains **certifiably fully RFC compliant**.

Under the canonical `0.3.9` promoted release root, the package is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.

What is currently true:

- the public package version is `0.3.9`
- the canonical release root is `docs/review/conformance/releases/0.3.9/release-0.3.9/`
- the historical released `0.3.8` root remains preserved and immutable
- RFC 9220 WebSocket-over-HTTP/3 remains green in both the authoritative boundary and the promoted root
- the flag surface is green
- the operator surface is green
- the performance surface is green
- the documentation surface is green
- the composite promotion target is green

There are no open in-bounds certification blockers for the current `0.3.9` line.

## Canonical current-state chain

Use these sources for package-wide truth:

- `CURRENT_REPOSITORY_STATE.md`
- `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- `docs/review/conformance/current_state_chain.current.json`
- `docs/review/conformance/package_compliance_review_phase9i.current.json`
- `docs/review/conformance/release_gate_status.current.json`

Additional focused audits such as `docs/review/conformance/http_integrity_caching_signatures_status.current.json` and `docs/review/conformance/rfc_applicability_and_competitor_status.current.json` remain current for their own scopes, but they are **not** the canonical package-wide current-state source.

## Governance and documentation organization

The mutable documentation entrypoint is now `docs/README.md`.

The governance entrypoints are:

- `docs/gov/README.md`
- `docs/gov/tree.md`
- `docs/gov/mut.md`
- `docs/gov/release.md`

The agent-facing execution guide is `AGENTS.md`.

Current layout policy:

- new mutable docs belong under `docs/`
- release/evidence roots are immutable and marked by `MUT.json`
- folder state resolves by nearest-ancestor-wins
- `python tools/govchk.py state PATH` resolves mutability
- `python tools/govchk.py scan` enforces mutable naming/path limits

Historical root archival notes remain grandfathered for provenance and test stability. New mutable root notes are not part of the sustainable layout.

## Current release and artifact pointers

Primary documentation for the promoted state lives in:

- `README.md`
- `RELEASE_NOTES_0.3.9.md`
- `docs/review/conformance/README.md`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`

Current scoped comparison/audit companions:

- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md`
- `docs/comp/rfc.md`
- `docs/comp/cli.md`
- `docs/comp/ops.md`
- `docs/comp/oob.md`

The current public lifecycle and embedder contract is documented in `docs/LIFECYCLE_AND_EMBEDDED_SERVER.md`.

The canonical current integrated Phase 4 example tree is `examples/advanced_delivery/`. The retained `examples/advanced_protocol_delivery/` tree is an archival compatibility path for the original Phase 4 checkpoint examples.

## Current external publication note

External publication is an operator action outside the repository. The repository target is `0.3.9`; consult the package index before claiming that a new external publish has occurred.

## Certification environment freeze

The strict-promotion certification environment contract remains preserved in:

- `docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md`
- `docs/review/conformance/certification_environment_freeze.current.json`
- `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-certification-environment-bundle/`

The frozen release workflow remains Python 3.11 or 3.12 with `.[certification,dev]` installed before the release workflow runs.

## Historical compatibility notes

Canonical promotion was **not** performed for the frozen `0.3.7` candidate next release root. That statement remains historically accurate for `docs/review/conformance/PHASE7_CANONICAL_PROMOTION_STATUS.md` and is preserved here for compatibility with the Phase 7 audit trail.

Historical checkpoint guardrail: the authoritative boundary remains green while the strict target is not yet green. That sentence is retained only as a historical compatibility phrase for earlier checkpoint/test references; it is not the current release truth for `0.3.9`.



## Phase 9A promotion-contract-freeze checkpoint

The preserved Phase 9A contract-freeze records remain in-tree for provenance:

- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/phase9a_execution_backlog.current.json`

Those records remain historical closure material rather than competing current-state sources for the promoted `0.3.9` line.

## Phase 9 implementation-plan checkpoint

The preserved execution-plan and closure chain remains documented in:

- `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/phase9_implementation_plan.current.json`
- `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/phase9a_promotion_contract.current.json`
- `docs/review/conformance/PHASE9B_INDEPENDENT_HARNESS_FOUNDATION.md`
- `docs/review/conformance/phase9b_independent_harness.current.json`

Those records remain in-tree for provenance. They are not competing current-state sources for the promoted `0.3.9` line.
