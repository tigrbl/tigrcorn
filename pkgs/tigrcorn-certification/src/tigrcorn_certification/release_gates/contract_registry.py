from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *
from .independent import *

def evaluate_contract_registry_release_gate(
    source_root: str | Path,
    *,
    boundary: Mapping[str, Any] | None = None,
    contract_registry_path: str | Path | None = None,
    require_ssot_links: bool = False,
    checked_files: list[str] | None = None,
    artifact_status: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    source_root = Path(source_root)
    boundary = dict(boundary or {})
    registry_payload = _load_contract_registry_payload(
        source_root,
        boundary=boundary,
        contract_registry_path=contract_registry_path,
        checked_files=checked_files,
    )
    failures = _evaluate_contract_registry_payload(registry_payload)
    if require_ssot_links:
        failures.extend(
            _evaluate_contract_registry_ssot_links(
                source_root=source_root,
                registry_payload=registry_payload,
                checked_files=checked_files,
            )
        )
    if artifact_status is not None:
        artifact_status['contract_registry'] = {
            'contract_count': len(registry_payload.get('contracts', [])) if isinstance(registry_payload.get('contracts'), list) else 0,
            'failed': bool(failures),
            'require_ssot_links': require_ssot_links,
        }
    return failures
def _load_contract_registry_payload(
    source_root: Path,
    *,
    boundary: Mapping[str, Any],
    contract_registry_path: str | Path | None,
    checked_files: list[str] | None,
) -> dict[str, Any]:
    registry_path_value = contract_registry_path or boundary.get('contract_registry')
    if registry_path_value is not None:
        registry_path = source_root / Path(registry_path_value)
        if checked_files is not None:
            checked_files.append(str(registry_path))
        if not registry_path.exists():
            return {'contracts': [], '_load_failure': f'missing contract registry file: {registry_path}'}
        return json.loads(registry_path.read_text(encoding='utf-8'))

    from tigrcorn_contract.registry import export_contract_registry

    return export_contract_registry()


def _evaluate_contract_registry_payload(registry_payload: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    load_failure = registry_payload.get('_load_failure')
    if isinstance(load_failure, str) and load_failure:
        return [load_failure]
    contracts = registry_payload.get('contracts')
    if not isinstance(contracts, list):
        return ['contract registry is missing a contracts list']
    if not contracts:
        failures.append('contract registry does not declare any contracts')

    seen_ids: set[str] = set()
    for contract in contracts:
        if not isinstance(contract, Mapping):
            failures.append('contract registry contains a malformed contract record')
            continue
        contract_id = str(contract.get('contract_id', '')).strip()
        if not contract_id:
            failures.append('contract registry contains a contract without contract_id')
            continue
        if contract_id in seen_ids:
            failures.append(f'contract registry contains duplicate contract_id: {contract_id}')
        seen_ids.add(contract_id)
        failures.extend(_evaluate_contract_release_traceability(contract_id, contract))
    return failures


def _evaluate_contract_release_traceability(contract_id: str, contract: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    traceability = contract.get('traceability', {})
    if not isinstance(traceability, Mapping):
        traceability = {}
    certified = bool(contract.get('certified', False))
    release_certified = bool(traceability.get('release_certified', False))
    stability = str(contract.get('stability', '')).strip()

    if stability == 'deprecated':
        if certified or release_certified:
            failures.append(f'deprecated contract {contract_id} cannot be release certified')
        if not contract.get('replacement_contract_id'):
            failures.append(f'deprecated contract {contract_id} must declare replacement_contract_id')
        if not contract.get('retirement_note'):
            failures.append(f'deprecated contract {contract_id} must declare retirement_note')
        return failures

    if not certified and not release_certified:
        return failures

    if stability != 'certified':
        failures.append(f'certified contract {contract_id} must use certified stability')
    if not bool(contract.get('implemented', False)):
        failures.append(f'certified contract {contract_id} must be implemented')
    if str(traceability.get('status', '')).strip() != 'complete':
        failures.append(f'certified contract {contract_id} must have complete traceability')
    if not release_certified:
        failures.append(f'certified contract {contract_id} must set traceability.release_certified')
    for field_name in ('rfcs', 'spec_ids', 'implementation_refs', 'test_ids', 'evidence_ids', 'negative_test_ids'):
        values = traceability.get(field_name)
        if not isinstance(values, list) or not values:
            failures.append(f'certified contract {contract_id} is missing traceability.{field_name}')
    return failures


def _evaluate_contract_registry_ssot_links(
    *,
    source_root: Path,
    registry_payload: Mapping[str, Any],
    checked_files: list[str] | None,
) -> list[str]:
    ssot_path = source_root / DEFAULT_SSOT_REGISTRY_PATH
    if checked_files is not None:
        checked_files.append(str(ssot_path))
    if not ssot_path.exists():
        return [f'missing SSOT registry for contract traceability links: {ssot_path}']
    ssot_payload = json.loads(ssot_path.read_text(encoding='utf-8'))
    id_sets = {
        'spec_ids': {str(item.get('id')) for item in ssot_payload.get('specs', []) if isinstance(item, Mapping)},
        'test_ids': {str(item.get('id')) for item in ssot_payload.get('tests', []) if isinstance(item, Mapping)},
        'evidence_ids': {str(item.get('id')) for item in ssot_payload.get('evidence', []) if isinstance(item, Mapping)},
    }
    failures: list[str] = []
    for contract in registry_payload.get('contracts', []):
        if not isinstance(contract, Mapping):
            continue
        traceability = contract.get('traceability', {})
        if not isinstance(traceability, Mapping) or not (contract.get('certified') or traceability.get('release_certified')):
            continue
        contract_id = str(contract.get('contract_id'))
        for field_name, known_ids in id_sets.items():
            for linked_id in traceability.get(field_name, []):
                if str(linked_id) not in known_ids:
                    failures.append(f'contract {contract_id} references unknown SSOT {field_name[:-4]} id: {linked_id}')
    return failures


def _evaluate_rfc_evidence(
    *,
    source_root: Path,
    boundary: dict[str, Any],
    corpus_payload: dict[str, Any],
    independent_matrix_scenarios: list[InteropScenario],
    same_stack_matrix_scenarios: list[InteropScenario],
    checked_files: list[str],
    rfc_status: dict[str, dict[str, Any]],
    artifact_status: dict[str, dict[str, Any]],
) -> list[str]:
    failures: list[str] = []
    required_rfcs = [str(item) for item in boundary.get('required_rfcs', [])]
    rfc_evidence_map = dict(boundary.get('required_rfc_evidence', {}))
    corpus_vectors = _index_corpus_vectors(corpus_payload)
    independent_index = {scenario.id: scenario for scenario in independent_matrix_scenarios}
    same_stack_index = {scenario.id: scenario for scenario in same_stack_matrix_scenarios}
    artifact_bundles = {tier: source_root / Path(path) for tier, path in dict(boundary.get('artifact_bundles', {})).items()}

    for bundle_root in artifact_bundles.values():
        checked_files.extend(str(path) for path in [bundle_root, bundle_root / 'index.json', bundle_root / 'manifest.json'])

    preserved_artifacts = {
        tier: _load_preserved_artifacts(bundle_root, artifact_status=artifact_status)
        for tier, bundle_root in artifact_bundles.items()
    }

    for required_rfc in required_rfcs:
        policy = rfc_evidence_map.get(required_rfc)
        if not isinstance(policy, Mapping):
            failures.append(f'boundary required RFC is missing evidence policy: {required_rfc}')
            continue
        highest_tier = str(policy.get('highest_required_evidence_tier', '')).strip()
        declared_evidence = dict(policy.get('declared_evidence', {}))
        rfc_failures, status = _evaluate_single_rfc_policy(
            required_rfc=required_rfc,
            highest_tier=highest_tier,
            declared_evidence=declared_evidence,
            corpus_vectors=corpus_vectors,
            independent_index=independent_index,
            same_stack_index=same_stack_index,
            preserved_artifacts=preserved_artifacts,
        )
        failures.extend(rfc_failures)
        rfc_status[required_rfc] = status

    extra_policies = sorted(set(rfc_evidence_map) - set(required_rfcs))
    for item in extra_policies:
        failures.append(f'boundary contains evidence policy for non-required RFC: {item}')

    return failures


def _evaluate_single_rfc_policy(
    *,
    required_rfc: str,
    highest_tier: str,
    declared_evidence: dict[str, Any],
    corpus_vectors: dict[str, dict[str, Any]],
    independent_index: dict[str, InteropScenario],
    same_stack_index: dict[str, InteropScenario],
    preserved_artifacts: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    status: dict[str, Any] = {
        'highest_required_evidence_tier': highest_tier,
        'declared_evidence': declared_evidence,
        'resolved_evidence': {},
        'highest_observed_evidence_tier': None,
    }

    if highest_tier not in EVIDENCE_TIER_ORDER:
        failures.append(f'{required_rfc} has invalid highest_required_evidence_tier {highest_tier!r}')
        return failures, status

    if highest_tier not in declared_evidence:
        failures.append(f'{required_rfc} requires {highest_tier} evidence but does not declare any {highest_tier} sources')

    observed_rank = 0
    for tier_name, entries in declared_evidence.items():
        if tier_name not in EVIDENCE_TIER_ORDER:
            failures.append(f'{required_rfc} declares invalid evidence tier {tier_name!r}')
            continue
        if not isinstance(entries, list) or not all(isinstance(item, str) for item in entries):
            failures.append(f'{required_rfc} declares malformed evidence list for {tier_name}')
            continue
        resolved: list[dict[str, Any]] = []
        tier_failures, tier_satisfied = _resolve_declared_evidence(
            required_rfc=required_rfc,
            tier_name=tier_name,
            entries=entries,
            corpus_vectors=corpus_vectors,
            independent_index=independent_index,
            same_stack_index=same_stack_index,
            preserved_artifacts=preserved_artifacts,
            resolved=resolved,
        )
        failures.extend(tier_failures)
        status['resolved_evidence'][tier_name] = resolved
        if tier_satisfied:
            observed_rank = max(observed_rank, EVIDENCE_TIER_ORDER[tier_name])

    if observed_rank == 0:
        failures.append(f'{required_rfc} does not resolve any declared evidence')
    elif observed_rank < EVIDENCE_TIER_ORDER[highest_tier]:
        observed_tier = VALID_EVIDENCE_TIERS[observed_rank - 1]
        failures.append(
            f'{required_rfc} requires {highest_tier} evidence, but the resolved evidence only reaches {observed_tier}'
        )
        status['highest_observed_evidence_tier'] = observed_tier
    else:
        status['highest_observed_evidence_tier'] = VALID_EVIDENCE_TIERS[observed_rank - 1]

    return failures, status


def _resolve_declared_evidence(
    *,
    required_rfc: str,
    tier_name: str,
    entries: list[str],
    corpus_vectors: dict[str, dict[str, Any]],
    independent_index: dict[str, InteropScenario],
    same_stack_index: dict[str, InteropScenario],
    preserved_artifacts: dict[str, dict[str, dict[str, Any]]],
    resolved: list[dict[str, Any]],
) -> tuple[list[str], bool]:
    failures: list[str] = []
    tier_satisfied = True
    for entry in entries:
        if tier_name == 'local_conformance':
            vector = corpus_vectors.get(entry)
            if vector is None:
                failures.append(f'{required_rfc} references unknown local_conformance vector {entry}')
                tier_satisfied = False
                continue
            resolved.append({'vector': entry, 'rfc': _normalize_rfc_from_corpus(vector.get('rfc'))})
            continue

        scenario_index = independent_index if tier_name == 'independent_certification' else same_stack_index
        scenario = scenario_index.get(entry)
        if scenario is None:
            failures.append(f'{required_rfc} references unknown {tier_name} scenario {entry}')
            tier_satisfied = False
            continue
        rfcs = set(_scenario_rfcs(scenario))
        if required_rfc not in rfcs:
            failures.append(f'{required_rfc} references scenario {entry} but that scenario metadata does not declare {required_rfc}')
            tier_satisfied = False
        scenario_payload = {
            'scenario_id': entry,
            'enabled': bool(scenario.enabled and scenario.peer_process.enabled and scenario.sut.enabled),
            'peer_kind': scenario.peer_process.provenance_kind,
        }
        if tier_name == 'independent_certification':
            bundle_status = preserved_artifacts.get('independent_certification', {}).get(entry)
            if bundle_status is None:
                failures.append(
                    f'{required_rfc} independent_certification scenario {entry} is missing preserved artifacts under the canonical independent release bundle'
                )
                scenario_payload['artifact_status'] = 'missing'
                tier_satisfied = False
            elif not bundle_status.get('passed', False):
                failures.append(
                    f'{required_rfc} independent_certification scenario {entry} has preserved artifacts but they are not marked passing'
                )
                scenario_payload['artifact_status'] = 'failed'
                tier_satisfied = False
            else:
                scenario_payload['artifact_status'] = 'passed'
            if not scenario_payload['enabled']:
                failures.append(f'{required_rfc} independent_certification scenario {entry} is declared but disabled')
                tier_satisfied = False
        elif tier_name == 'same_stack_replay':
            bundle_status = preserved_artifacts.get('same_stack_replay', {}).get(entry)
            scenario_payload['artifact_status'] = 'passed' if bundle_status and bundle_status.get('passed', False) else 'missing'
            if bundle_status is None:
                failures.append(f'{required_rfc} same_stack_replay scenario {entry} is missing preserved artifacts under the canonical same-stack bundle')
                tier_satisfied = False
        resolved.append(scenario_payload)
    return failures, tier_satisfied

__all__ = [name for name in globals() if not name.startswith('__')]

