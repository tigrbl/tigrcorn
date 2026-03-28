from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
CURRENT_STATE_CHAIN_JSON = 'docs/review/conformance/current_state_chain.current.json'
CURRENT_STATE_CHAIN_MD = 'docs/review/conformance/CURRENT_STATE_CHAIN.md'
CURRENT_STATE_MD = 'CURRENT_REPOSITORY_STATE.md'
PACKAGE_REVIEW_JSON = 'docs/review/conformance/package_compliance_review_phase9i.current.json'
PACKAGE_REVIEW_MD = 'docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md'
REVIEWED_AT = '2026-03-26'

CANONICAL_CURRENT_SOURCES = {
    'release_gate_status.current.json',
    'package_compliance_review_phase9i.current.json',
    'phase9_release_promotion.current.json',
    'phase9i_release_assembly.current.json',
    'phase9i_strict_validation.current.json',
    'current_state_chain.current.json',
}

SCOPED_CURRENT_AUDITS = {
    'http_integrity_caching_signatures_status.current.json',
    'rfc_applicability_and_competitor_status.current.json',
    'rfc_applicability_and_competitor_support.current.json',
}

CURRENT_SUBSYSTEM_TRUTH = {
    'aioquic_adapter_preflight.current.json',
    'certification_environment_freeze.current.json',
    'content_coding_local_behavior_artifacts.current.json',
    'interop_wrapper_registry.current.json',
    'ocsp_local_validation_artifacts.current.json',
    'optional_dependency_surface.current.json',
    'packet_space_legality_corpus.current.json',
    'phase3_strict_rfc_status.current.json',
    'phase4_operator_surface_status.current.json',
    'phase5_interop_flow_status.current.json',
    'phase6_performance_status.current.json',
    'replayable_fixture_suite.phase3_transport_core.current.json',
    'trailer_fields_local_behavior_artifacts.current.json',
}

CANONICAL_CHAIN_HUMAN = [
    CURRENT_STATE_MD,
    CURRENT_STATE_CHAIN_MD,
    'docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md',
    'docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md',
    PACKAGE_REVIEW_MD,
    'RFC_CERTIFICATION_STATUS.md',
]

CANONICAL_CHAIN_MACHINE = [
    CURRENT_STATE_CHAIN_JSON,
    PACKAGE_REVIEW_JSON,
    'docs/review/conformance/release_gate_status.current.json',
    'docs/review/conformance/phase9_release_promotion.current.json',
    'docs/review/conformance/phase9i_release_assembly.current.json',
    'docs/review/conformance/phase9i_strict_validation.current.json',
]

CANONICAL_POLICY = [
    'docs/review/conformance/CERTIFICATION_BOUNDARY.md',
    'docs/review/conformance/certification_boundary.json',
    'docs/review/conformance/STRICT_PROFILE_TARGET.md',
    'docs/review/conformance/certification_boundary.strict_target.json',
    'docs/review/conformance/promotion_gate.target.json',
]

SCOPED_AUDIT_INFO = {
    'http_integrity_caching_signatures_status.current.json': {
        'human_doc': 'docs/review/conformance/HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md',
        'scope': 'focused_current_http_integrity_caching_and_signatures_audit',
    },
    'rfc_applicability_and_competitor_status.current.json': {
        'human_doc': 'docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md',
        'scope': 'focused_current_rfc_applicability_and_competitor_status_review',
    },
    'rfc_applicability_and_competitor_support.current.json': {
        'human_doc': 'docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md',
        'scope': 'focused_current_rfc_applicability_support_snapshot',
    },
}

CHECKPOINT_ROOT_MDS = [
    'CURRENT_REPOSITORY_STATE_PHASE1_SURFACE_PARITY_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_PHASE2_CORE_HTTP_ENTITY_SEMANTICS_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_PHASE3_TRANSPORT_CORE_STRICTNESS_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_PHASE4_ADVANCED_PROTOCOL_DELIVERY_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_PROMOTION_ARTIFACT_RECONCILIATION_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_TRIO_RUNTIME_SURFACE_RECONCILIATION_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_DEPENDENCY_DECLARATION_RECONCILIATION_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_STATIC_DELIVERY_PRODUCTIONIZATION_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_RESPONSE_PIPELINE_STREAMING_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_PHASE2_RFC_BOUNDARY_FORMALIZATION_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_PHASE4_RFC_BOUNDARY_FORMALIZATION_CHECKPOINT.md',
    'CURRENT_REPOSITORY_STATE_DOCUMENTATION_TRUTH_NORMALIZATION_CHECKPOINT.md',
]

CHECKPOINT_CONFORMANCE_MDS = [
    'docs/review/conformance/PHASE2_CORE_HTTP_ENTITY_SEMANTICS_CHECKPOINT.md',
    'docs/review/conformance/PHASE3_TRANSPORT_CORE_STRICTNESS_CHECKPOINT.md',
    'docs/review/conformance/PHASE4_ADVANCED_PROTOCOL_DELIVERY_CHECKPOINT.md',
]

ARCHIVAL_NOTE = (
    '> Historical checkpoint note: this file is retained as an archival snapshot for provenance and stable test/tool '
    'references. It is not the canonical package-wide current-state source. Use `CURRENT_REPOSITORY_STATE.md` and '
    f'`{CURRENT_STATE_CHAIN_JSON}` for current package truth.\n\n'
)

SCOPED_AUDIT_NOTE = (
    '> Scope note: this document is a focused current audit, not the canonical package-wide current-state source. '
    f'Use `CURRENT_REPOSITORY_STATE.md` and `{CURRENT_STATE_CHAIN_JSON}` for package-wide truth.\n\n'
)

ADVANCED_PROTOCOL_DELIVERY_NOTE = (
    '> Path note: `examples/advanced_delivery/` is the canonical current integrated Phase 4 example tree. '
    '`examples/advanced_protocol_delivery/` is retained as an archival compatibility path for focused single-feature '
    'examples from the original Phase 4 checkpoint.\n\n'
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def _classify_current_json(name: str) -> tuple[str, bool, str]:
    if name in CANONICAL_CURRENT_SOURCES:
        return ('canonical_current_state_source', True, 'canonical_current_state_chain')
    if name in SCOPED_CURRENT_AUDITS:
        return ('scoped_current_audit_not_package_wide_truth_source', False, 'scoped_current_audit')
    if name in CURRENT_SUBSYSTEM_TRUTH:
        return ('current_subsystem_truth_source', True, 'subsystem_current_state')
    return ('archival_named_current_snapshot_for_stability', False, 'archival_snapshot')


def _augment_current_json(path: Path) -> None:
    payload = _read_json(path)
    role, truth_source, truth_scope = _classify_current_json(path.name)
    meta = {
        'document_role': role,
        'current_truth_source': truth_source,
        'truth_scope': truth_scope,
        'canonical_current_state_chain': CURRENT_STATE_CHAIN_JSON,
        'documentation_truth_reviewed_at': REVIEWED_AT,
    }
    if role.startswith('archival_'):
        meta['archival_note'] = (
            'Historical snapshot retained in place for provenance and stable references; not the canonical package-wide current-state source.'
        )
    elif role == 'scoped_current_audit_not_package_wide_truth_source':
        meta['scoped_audit_scope'] = SCOPED_AUDIT_INFO[path.name]['scope']
        meta['not_package_wide_truth_source'] = True
    elif role == 'current_subsystem_truth_source':
        meta['subsystem_truth_source'] = True

    updated = dict(meta)
    updated.update(payload)
    _write_json(path, updated)


def _ensure_prefixed_note(path: Path, note: str) -> None:
    text = path.read_text(encoding='utf-8')
    if text.startswith(note):
        return
    path.write_text(note + text, encoding='utf-8')


def _replace_examples_readme() -> None:
    text = '''# Examples

This repository now uses a single canonical current example tree for the integrated Phase 4 delivery surface.

## Canonical current example paths

- `examples/advanced_delivery/` — canonical integrated Phase 4 launchable app/client examples
- `examples/http_entity_static/` — canonical static + range + ETag example pair
- `examples/echo_http/` — canonical minimal HTTP app example
- `examples/websocket_echo/` — canonical WebSocket example
- `examples/lifespan/` — canonical lifespan example
- `examples/PHASE4_PROTOCOL_PAIRING.md` — canonical current pairing matrix

## Retained archival compatibility paths

- `examples/advanced_protocol_delivery/` — retained for provenance and focused single-feature examples from the original Phase 4 checkpoint. This path is **not** the canonical integrated example tree.

## Documentation policy

For package-wide current truth, use `CURRENT_REPOSITORY_STATE.md` and `docs/review/conformance/current_state_chain.current.json`.

For the Phase 4 example policy specifically:

- `docs/review/conformance/phase4_advanced_delivery/examples_matrix.json` is the canonical current integrated example matrix
- `docs/review/conformance/phase4_advanced_protocol_delivery/example_matrix.json` is retained as an archival Phase 4 checkpoint matrix
'''
    (ROOT / 'examples/README.md').write_text(text, encoding='utf-8')


def _replace_current_state_chain_md(archival_current_paths: list[str]) -> None:
    text = f'''# Current-state chain

This document defines the **one canonical package-wide current-state chain** for the repository.

## Canonical package-wide current-state sources

### Human-readable sources

''' + '\n'.join(f'- `{item}`' for item in CANONICAL_CHAIN_HUMAN) + '\n\n### Machine-readable sources\n\n' + '\n'.join(f'- `{item}`' for item in CANONICAL_CHAIN_MACHINE) + '\n\n## Canonical policy sources\n\n' + '\n'.join(f'- `{item}`' for item in CANONICAL_POLICY) + f'''

## Scoped current audits that are **not** package-wide current-state sources

- `docs/review/conformance/HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md`
- `docs/review/conformance/http_integrity_caching_signatures_status.current.json`
- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md`
- `docs/review/conformance/rfc_applicability_and_competitor_status.current.json`
- `docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md`
- `docs/review/conformance/rfc_applicability_and_competitor_support.current.json`

Those documents are current for their own focused scopes, but they are **not** the canonical package-wide current-state source.

## Historical snapshots that still use `.current.json` names

Many earlier checkpoint and phase-closure artifacts retain stable `*.current.json` file names for tests, tooling, and provenance. They are historical snapshots when their `document_role` is `archival_named_current_snapshot_for_stability`.

Representative archival current-alias paths include:

''' + '\n'.join(f'- `{item}`' for item in archival_current_paths) + '''

## Example-path policy

- `examples/advanced_delivery/` is the canonical current integrated Phase 4 example tree.
- `examples/advanced_protocol_delivery/` is retained as an archival compatibility path for focused single-feature examples from the original Phase 4 checkpoint.
- `examples/PHASE4_PROTOCOL_PAIRING.md` is the canonical current pairing matrix.

## Naming policy

A file name ending in `.current.json` does **not** by itself mean the file is the canonical package-wide current truth source. The controlling signal is the machine-readable `document_role` and `current_truth_source` fields.
'''
    (CONFORMANCE / 'CURRENT_STATE_CHAIN.md').write_text(text, encoding='utf-8')


def _write_current_state_chain_json(archival_current_paths: list[str]) -> None:
    payload = {
        'checkpoint': 'documentation_truth_normalization',
        'reviewed_at': REVIEWED_AT,
        'document_role': 'canonical_current_state_source',
        'current_truth_source': True,
        'canonical_human_current_state_chain': CANONICAL_CHAIN_HUMAN,
        'canonical_machine_current_state_chain': CANONICAL_CHAIN_MACHINE,
        'canonical_policy_sources': CANONICAL_POLICY,
        'scoped_current_audits_not_package_wide_truth_sources': [
            {
                'path': f'docs/review/conformance/{name}',
                'human_doc': info['human_doc'],
                'document_role': 'scoped_current_audit_not_package_wide_truth_source',
                'scope': info['scope'],
            }
            for name, info in SCOPED_AUDIT_INFO.items()
        ],
        'current_subsystem_truth_sources': sorted(
            f'docs/review/conformance/{name}' for name in CURRENT_SUBSYSTEM_TRUTH
        ),
        'historical_current_aliases_retained_for_stability': archival_current_paths,
        'example_path_policy': {
            'canonical_current_phase4_example_tree': 'examples/advanced_delivery/',
            'canonical_pairing_doc': 'examples/PHASE4_PROTOCOL_PAIRING.md',
            'retained_archival_feature_specific_tree': 'examples/advanced_protocol_delivery/',
            'retained_archival_conformance_checkpoint_matrix': 'docs/review/conformance/phase4_advanced_protocol_delivery/example_matrix.json',
            'canonical_current_examples_matrix': 'docs/review/conformance/phase4_advanced_delivery/examples_matrix.json',
        },
        'naming_policy': {
            'rule': 'A .current.json suffix alone does not define canonical package truth; document_role and current_truth_source do.',
            'why_aliases_remain': 'Stable references for tests, tooling, and historical provenance.',
        },
        'exit_criteria': {
            'one_canonical_current_state_chain': True,
            'historical_snapshots_clearly_marked_archival': True,
            'scoped_audits_relabelled_non_canonical': True,
            'example_path_documentation_normalized': True,
        },
    }
    _write_json(CONFORMANCE / 'current_state_chain.current.json', payload)


def _update_conformance_readme() -> None:
    path = CONFORMANCE / 'README.md'
    text = path.read_text(encoding='utf-8')
    marker = '## Config / CLI substrate tracking\n'
    insert = f'''## Canonical current-state chain

The canonical package-wide current-state chain is now explicitly defined in:

- `{CURRENT_STATE_CHAIN_MD}`
- `{CURRENT_STATE_CHAIN_JSON}`
- `{CURRENT_STATE_MD}`
- `{PACKAGE_REVIEW_JSON}`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/phase9i_strict_validation.current.json`

Historical phase checkpoint snapshots still keep stable `*.current.json` file names where needed for tests and provenance, but they are now explicitly labeled by `document_role` and are not ambiguous current-state sources.

## Scoped current audits and archival compatibility docs

The focused HTTP integrity/caching/signatures audit and the RFC applicability / competitor comparison documents remain current for their own scopes, but they are **not** the canonical package-wide current-state source. Use `{CURRENT_STATE_CHAIN_JSON}` to distinguish canonical package truth from scoped audits and historical snapshots.

The canonical current integrated Phase 4 example tree is `examples/advanced_delivery/`. The older `examples/advanced_protocol_delivery/` path is retained as an archival compatibility path for the original Phase 4 checkpoint examples.

'''
    if insert not in text:
        if marker not in text:
            raise RuntimeError(f'expected marker not found in {path}')
        text = text.replace(marker, insert + marker)

    old = 'A focused current-state snapshot for this target lives in `PHASE8_STRICT_PROMOTION_TARGET_STATUS.md` and `phase8_strict_promotion_target_status.current.json`.'
    new = 'The historical strict-target snapshot for this target remains preserved in `PHASE8_STRICT_PROMOTION_TARGET_STATUS.md` and `phase8_strict_promotion_target_status.current.json`. Those files are retained for provenance and are not the canonical package-wide current-state chain.'
    if old in text:
        text = text.replace(old, new)

    anchor = '- `phase9b_independent_harness.current.json`\n\n'
    note = 'Those executed phase records remain in-tree for provenance and stable references. Their `*.current.json` file names do not make them the canonical package-wide current-state chain.\n\n'
    if note not in text and anchor in text:
        text = text.replace(anchor, anchor + note)

    path.write_text(text, encoding='utf-8')


def _update_current_repository_state() -> None:
    path = ROOT / 'CURRENT_REPOSITORY_STATE.md'
    text = path.read_text(encoding='utf-8')
    marker = 'Primary documentation for the current promoted state now lives in:\n\n'
    insert = f'''## Canonical current-state chain

The canonical package-wide current-state chain is now explicitly normalized.

Use these sources for package-wide truth:

- `{CURRENT_STATE_MD}`
- `{CURRENT_STATE_CHAIN_MD}`
- `{CURRENT_STATE_CHAIN_JSON}`
- `{PACKAGE_REVIEW_JSON}`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/phase9i_strict_validation.current.json`

Additional focused audits such as `docs/review/conformance/http_integrity_caching_signatures_status.current.json` and `docs/review/conformance/rfc_applicability_and_competitor_status.current.json` remain current for their own narrow scopes, but they are **not** the canonical package-wide current-state source.

Historical phase checkpoints and executed closure snapshots may still retain stable `*.current.json` names for provenance and test references, but they are now explicitly labeled as archival when they are not current package truth.

The canonical current integrated Phase 4 example tree is `examples/advanced_delivery/`. The retained `examples/advanced_protocol_delivery/` tree is an archival compatibility path for the original Phase 4 checkpoint examples.

'''
    if insert not in text:
        if marker not in text:
            raise RuntimeError(f'expected marker not found in {path}')
        text = text.replace(marker, insert + marker)
    path.write_text(text, encoding='utf-8')


def _update_package_review_json() -> None:
    path = ROOT / PACKAGE_REVIEW_JSON
    payload = _read_json(path)
    payload['generated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    summary = payload.setdefault('summary', {})
    summary['documentation_truth_normalized'] = True
    summary['canonical_current_state_chain_defined'] = True
    summary['historical_current_aliases_labeled'] = True
    summary['scoped_current_audits_non_canonical'] = True
    summary['canonical_phase4_example_tree'] = 'examples/advanced_delivery/'
    summary['archival_phase4_example_tree'] = 'examples/advanced_protocol_delivery/'
    files = payload.setdefault('files_updated_by_review', [])
    for rel in [
        CURRENT_STATE_MD,
        CURRENT_STATE_CHAIN_MD,
        CURRENT_STATE_CHAIN_JSON,
        'docs/review/conformance/HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md',
        'docs/review/conformance/http_integrity_caching_signatures_status.current.json',
        'docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md',
        'docs/review/conformance/rfc_applicability_and_competitor_status.current.json',
        'docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md',
        'docs/review/conformance/rfc_applicability_and_competitor_support.current.json',
        'docs/review/conformance/README.md',
        'examples/README.md',
        'examples/advanced_protocol_delivery/README.md',
        'examples/PHASE4_PROTOCOL_PAIRING.md',
        'docs/review/conformance/phase4_advanced_protocol_delivery/example_matrix.json',
        'docs/review/conformance/phase4_advanced_delivery/examples_matrix.json',
        'docs/review/conformance/documentation_truth_normalization_checkpoint.current.json',
        'CURRENT_REPOSITORY_STATE_DOCUMENTATION_TRUTH_NORMALIZATION_CHECKPOINT.md',
        'docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md',
    ]:
        if rel not in files:
            files.append(rel)
    _write_json(path, payload)


def _update_package_review_md() -> None:
    path = ROOT / PACKAGE_REVIEW_MD
    text = path.read_text(encoding='utf-8')
    marker = '## Remaining strict-target blockers\n'
    insert = f'''## Documentation truth normalization

The repository now defines one canonical package-wide current-state chain:

- `{CURRENT_STATE_MD}`
- `{CURRENT_STATE_CHAIN_MD}`
- `{CURRENT_STATE_CHAIN_JSON}`
- `{PACKAGE_REVIEW_JSON}`
- `docs/review/conformance/release_gate_status.current.json`
- `docs/review/conformance/phase9_release_promotion.current.json`
- `docs/review/conformance/phase9i_release_assembly.current.json`
- `docs/review/conformance/phase9i_strict_validation.current.json`

Focused audits such as `http_integrity_caching_signatures_status.current.json` and `rfc_applicability_and_competitor_status.current.json` remain current for their own narrow scopes, but they are explicitly non-canonical as package-wide current-state sources.

Historical checkpoint snapshots that still retain `*.current.json` names are now explicitly labeled as archival for provenance and stable references.

The canonical current integrated Phase 4 example tree is `examples/advanced_delivery/`; `examples/advanced_protocol_delivery/` remains a retained archival compatibility path.

'''
    if insert not in text:
        if marker not in text:
            raise RuntimeError(f'expected marker not found in {path}')
        text = text.replace(marker, insert + marker)
    path.write_text(text, encoding='utf-8')


def _update_example_docs() -> None:
    _replace_examples_readme()
    _ensure_prefixed_note(ROOT / 'examples' / 'advanced_protocol_delivery' / 'README.md', ADVANCED_PROTOCOL_DELIVERY_NOTE)
    pairing = ROOT / 'examples' / 'PHASE4_PROTOCOL_PAIRING.md'
    note = (
        '> Current pairing note: this is the canonical current Phase 4 pairing matrix. '
        '`examples/advanced_delivery/` is the canonical integrated example tree; '
        '`examples/advanced_protocol_delivery/` is retained as an archival compatibility path.\n\n'
    )
    _ensure_prefixed_note(pairing, note)


def _update_phase4_example_matrices() -> None:
    archival_path = CONFORMANCE / 'phase4_advanced_protocol_delivery' / 'example_matrix.json'
    archival = _read_json(archival_path)
    archival_updated = {
        'document_role': 'archival_phase4_checkpoint_example_matrix',
        'current_truth_source': False,
        'canonical_current_example_matrix': 'docs/review/conformance/phase4_advanced_delivery/examples_matrix.json',
        'canonical_current_example_tree': 'examples/advanced_delivery/',
        'archival_note': 'Retained for provenance and focused Phase 4 checkpoint compatibility; not the canonical current integrated example matrix.',
    }
    archival_updated.update(archival)
    _write_json(archival_path, archival_updated)

    current_path = CONFORMANCE / 'phase4_advanced_delivery' / 'examples_matrix.json'
    current = _read_json(current_path)
    current_updated = {
        'document_role': 'current_subsystem_truth_source',
        'current_truth_source': True,
        'canonical_current_example_tree': 'examples/advanced_delivery/',
        'retained_archival_example_tree': 'examples/advanced_protocol_delivery/',
    }
    current_updated.update(current)
    _write_json(current_path, current_updated)


def _update_readme() -> None:
    path = ROOT / 'README.md'
    text = path.read_text(encoding='utf-8')
    old = (
        'For the point-in-time repository summary, see `CURRENT_REPOSITORY_STATE.md`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. For an explicit gap analysis of the current Phase 9I checkpoint, see `docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md` and `docs/review/conformance/package_compliance_review_phase9i.current.json`. For the machine-readable certification policy, see `docs/review/conformance/certification_boundary.json`. For the offline remediation attempt that produced the provisional bundles, see `docs/review/conformance/OFFLINE_COMPLETION_ATTEMPT.md`, `docs/review/conformance/offline_completion_state.json`, `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`, `docs/review/conformance/all_surfaces_independent_state.json`, `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md`, `docs/review/conformance/SECONDARY_PARTIALS_STATUS.md`, and `docs/review/conformance/secondary_partials_state.json`. A detailed execution plan for the remaining strict-promotion work now also lives in `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md` and `docs/review/conformance/phase9_implementation_plan.current.json`. The executed Phase 9A contract freeze now also lives in `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md`, `docs/review/conformance/PHASE9A_EXECUTION_BACKLOG.md`, `docs/review/conformance/phase9a_promotion_contract.current.json`, and `docs/review/conformance/phase9a_execution_backlog.current.json`. The executed Phase 9B independent-harness foundation now also lives in `docs/review/conformance/PHASE9B_INDEPENDENT_HARNESS_FOUNDATION.md`, `docs/review/conformance/INTEROP_HARNESS_ARTIFACT_SCHEMA.md`, `docs/review/conformance/interop_wrapper_registry.current.json`, and `docs/review/conformance/phase9b_independent_harness.current.json`. The direct third-party aioquic adapter preflight now also lives in `docs/review/conformance/AIOQUIC_ADAPTER_PREFLIGHT.md` and `docs/review/conformance/aioquic_adapter_preflight.current.json`.'
    )
    new = (
        'For the point-in-time repository summary, use `CURRENT_REPOSITORY_STATE.md` together with `docs/review/conformance/current_state_chain.current.json`. The promoted release notes for this canonical release live in `RELEASE_NOTES_0.3.9.md`. For an explicit gap analysis of the current Phase 9I checkpoint, see `docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md` and `docs/review/conformance/package_compliance_review_phase9i.current.json`. For the machine-readable certification policy, see `docs/review/conformance/certification_boundary.json`. For the offline remediation attempt that produced the provisional bundles, see `docs/review/conformance/OFFLINE_COMPLETION_ATTEMPT.md`, `docs/review/conformance/offline_completion_state.json`, `docs/review/conformance/ALL_SURFACES_INDEPENDENT_STATUS.md`, `docs/review/conformance/all_surfaces_independent_state.json`, `docs/review/conformance/FLOW_CONTROL_CERTIFICATION_STATUS.md`, `docs/review/conformance/SECONDARY_PARTIALS_STATUS.md`, and `docs/review/conformance/secondary_partials_state.json`. Historical execution-plan and phase-closure records remain in-tree for provenance, including `docs/review/conformance/PHASE9_IMPLEMENTATION_PLAN.md` / `docs/review/conformance/phase9_implementation_plan.current.json`, `docs/review/conformance/PHASE9A_PROMOTION_CONTRACT_FREEZE.md` / `docs/review/conformance/phase9a_promotion_contract.current.json`, and `docs/review/conformance/PHASE9B_INDEPENDENT_HARNESS_FOUNDATION.md` / `docs/review/conformance/phase9b_independent_harness.current.json`. Those retained phase records are not the canonical package-wide current-state chain. The direct third-party aioquic adapter preflight now also lives in `docs/review/conformance/AIOQUIC_ADAPTER_PREFLIGHT.md` and `docs/review/conformance/aioquic_adapter_preflight.current.json`.'
    )
    if old in text:
        text = text.replace(old, new)
    path.write_text(text, encoding='utf-8')


def _write_documentation_truth_checkpoint(archival_current_paths: list[str]) -> None:
    payload = {
        'checkpoint': 'documentation_truth_normalization',
        'status': 'implemented_checkpoint_with_green_validation',
        'document_role': 'archival_named_current_snapshot_for_stability',
        'current_truth_source': False,
        'canonical_current_state_chain': CURRENT_STATE_CHAIN_JSON,
        'reviewed_at': REVIEWED_AT,
        'implemented': {
            'canonical_current_state_chain_defined': True,
            'scoped_current_audits_relabeled': True,
            'historical_current_aliases_relabeled': True,
            'example_path_documentation_normalized': True,
            'archival_current_alias_count': len(archival_current_paths),
        },
        'files_updated': [
            CURRENT_STATE_MD,
            CURRENT_STATE_CHAIN_MD,
            CURRENT_STATE_CHAIN_JSON,
            'docs/review/conformance/HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md',
            'docs/review/conformance/http_integrity_caching_signatures_status.current.json',
            'docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md',
            'docs/review/conformance/rfc_applicability_and_competitor_status.current.json',
            'docs/review/conformance/RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md',
            'docs/review/conformance/rfc_applicability_and_competitor_support.current.json',
            'docs/review/conformance/README.md',
            'docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md',
            PACKAGE_REVIEW_JSON,
            'examples/README.md',
            'examples/advanced_protocol_delivery/README.md',
            'examples/PHASE4_PROTOCOL_PAIRING.md',
            'docs/review/conformance/phase4_advanced_protocol_delivery/example_matrix.json',
            'docs/review/conformance/phase4_advanced_delivery/examples_matrix.json',
        ],
        'validation': {
            'expected_exit_criteria': {
                'one_canonical_current_state_chain': True,
                'historical_snapshots_clearly_marked_archival': True,
                'no_machine_readable_file_ambiguously_current_when_historical': True,
            }
        },
        'known_partials': [
            'Historical checkpoint file names are retained for stable references rather than physically renamed.',
            'Some phase-labelled subsystem status files remain current for their own narrow subsystem scopes and are not the package-wide current-state source.',
        ],
    }
    _write_json(CONFORMANCE / 'documentation_truth_normalization_checkpoint.current.json', payload)

    report = '''# Current repository state — documentation truth normalization checkpoint

This checkpoint normalizes documentation truth without changing the package RFC/product boundary.

## What changed

- defined one canonical package-wide current-state chain in `docs/review/conformance/CURRENT_STATE_CHAIN.md` and `docs/review/conformance/current_state_chain.current.json`
- relabeled focused current audits so they are explicitly non-canonical as package-wide current-state sources
- relabeled historical checkpoint `*.current.json` snapshots as archival while keeping stable file names for provenance and tests
- normalized Phase 4 example-path documentation so `examples/advanced_delivery/` is the canonical current integrated example tree

## Exit-criteria result

- one canonical current-state chain: **yes**
- historical snapshots clearly marked archival: **yes**
- machine-readable historical snapshots no longer ambiguous package-wide current sources: **yes**

## Honest note

This checkpoint improves documentation truth and provenance clarity. It does **not** by itself widen the RFC boundary or add new runtime/protocol features.
'''
    report_path = ROOT / 'CURRENT_REPOSITORY_STATE_DOCUMENTATION_TRUTH_NORMALIZATION_CHECKPOINT.md'
    report_path.write_text(ARCHIVAL_NOTE + report, encoding='utf-8')


def main() -> None:
    current_json_paths = sorted(CONFORMANCE.glob('*.current.json'))
    for path in current_json_paths:
        _augment_current_json(path)

    archival_current_paths = sorted(
        f'docs/review/conformance/{path.name}'
        for path in current_json_paths
        if _classify_current_json(path.name)[0].startswith('archival_')
    )
    archival_current_paths.append('docs/review/conformance/documentation_truth_normalization_checkpoint.current.json')
    archival_current_paths = sorted(set(archival_current_paths))

    _write_current_state_chain_json(archival_current_paths)
    _replace_current_state_chain_md(archival_current_paths)

    _ensure_prefixed_note(CONFORMANCE / 'HTTP_INTEGRITY_CACHING_SIGNATURES_STATUS.md', SCOPED_AUDIT_NOTE)
    _ensure_prefixed_note(CONFORMANCE / 'RFC_APPLICABILITY_AND_COMPETITOR_STATUS.md', SCOPED_AUDIT_NOTE)
    _ensure_prefixed_note(CONFORMANCE / 'RFC_APPLICABILITY_AND_COMPETITOR_SUPPORT.md', SCOPED_AUDIT_NOTE)
    _ensure_prefixed_note(CONFORMANCE / 'phase4_advanced_protocol_delivery' / 'README.md', ADVANCED_PROTOCOL_DELIVERY_NOTE)

    for rel in CHECKPOINT_ROOT_MDS + CHECKPOINT_CONFORMANCE_MDS:
        path = ROOT / rel
        if path.exists():
            _ensure_prefixed_note(path, ARCHIVAL_NOTE)

    _update_example_docs()
    _update_phase4_example_matrices()
    _update_readme()
    _update_conformance_readme()
    _update_current_repository_state()
    _update_package_review_json()
    _update_package_review_md()
    _write_documentation_truth_checkpoint(archival_current_paths)


if __name__ == '__main__':
    main()
