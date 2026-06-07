from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *

def _evaluate_documentation_claim_consistency(source_root: Path, config: Mapping[str, Any]) -> PromotionSectionReport:
    checks = list(config.get('required_phrase_checks', []))
    failures: list[str] = []
    checked_files: list[str] = []
    details: dict[str, Any] = {'documents_checked': len(checks)}

    for check in checks:
        if not isinstance(check, Mapping):
            failures.append(f'malformed documentation phrase check: {check!r}')
            continue
        doc_file = source_root / Path(str(check.get('path', '')))
        checked_files.append(str(doc_file))
        if not doc_file.exists():
            failures.append(f'missing documentation file for claim-consistency check: {doc_file}')
            continue
        text = doc_file.read_text(encoding='utf-8')
        for needle in [str(item) for item in check.get('must_contain', [])]:
            if needle not in text:
                failures.append(f'{doc_file} is missing required phrase: {needle!r}')
        for needle in [str(item) for item in check.get('must_not_contain', [])]:
            if needle in text:
                failures.append(f'{doc_file} contains forbidden phrase: {needle!r}')

    return PromotionSectionReport('documentation', not failures, failures, checked_files, details)


def _evaluate_governance_graph(*, source_root: Path, checked_files: list[str]) -> list[str]:
    failures: list[str] = []
    ssot_registry_path = source_root / DEFAULT_SSOT_REGISTRY_PATH
    claims_path = source_root / DEFAULT_CLAIMS_REGISTRY_PATH
    legacy_inventory_path = source_root / DEFAULT_LEGACY_UNITTEST_INVENTORY_PATH
    checked_files.extend(str(path) for path in (ssot_registry_path, claims_path, legacy_inventory_path))

    for path in (ssot_registry_path, claims_path, legacy_inventory_path):
        if not path.exists():
            failures.append(f'missing governance graph input: {path}')
    if failures:
        return failures

    ssot_payload = _load_json_payload(ssot_registry_path)
    repo = ssot_payload.get('repo', {})
    if str(repo.get('name', '')).strip() != 'tigrcorn':
        failures.append('ssot registry repo.name is not "tigrcorn"')
    active_boundary_id = str(ssot_payload.get('program', {}).get('active_boundary_id', '')).strip()
    active_release_id = str(ssot_payload.get('program', {}).get('active_release_id', '')).strip()
    if not active_boundary_id:
        failures.append('ssot registry is missing program.active_boundary_id')
    if not active_release_id:
        failures.append('ssot registry is missing program.active_release_id')
    boundaries = {
        str(row.get('id', '')): row
        for row in ssot_payload.get('boundaries', [])
        if isinstance(row, Mapping)
    }
    releases = {
        str(row.get('id', '')): row
        for row in ssot_payload.get('releases', [])
        if isinstance(row, Mapping)
    }
    if active_boundary_id not in boundaries:
        failures.append('ssot registry active boundary id does not resolve to a boundary row')
    if active_release_id not in releases:
        failures.append('ssot registry active release id does not resolve to a release row')
    if active_boundary_id in boundaries and boundaries[active_boundary_id].get('canonical_registry_source') != '.ssot/registry.json':
        failures.append('ssot registry active boundary does not self-identify .ssot/registry.json as canonical_registry_source')

    claims_payload = _load_json_payload(claims_path)
    claim_ids = {str(row.get('id', '')) for row in claims_payload.get('current_and_candidate_claims', []) if isinstance(row, Mapping)}
    ssot_claim_ids = {str(row.get('id', '')) for row in ssot_payload.get('claims', []) if isinstance(row, Mapping)}
    inventory_payload = _load_json_payload(legacy_inventory_path)

    risk_rows = ssot_payload.get('risks', [])
    if not isinstance(risk_rows, list):
        failures.append('ssot registry risk payload is malformed')
        return failures

    open_blocking_statuses = {'open', 'active', 'unmitigated', 'planned'}
    for row in risk_rows:
        if not isinstance(row, Mapping):
            continue
        risk_id = str(row.get('source_risk_id', row.get('id', '')))
        if bool(row.get('release_blocking', False)) and str(row.get('status', '')).strip().lower() in open_blocking_statuses:
            failures.append(f'blocking risk {risk_id} remains open with status={row.get("status")!r}')
        for claim_ref in row.get('claim_ids', []):
            claim_ref = str(claim_ref)
            if claim_ref not in ssot_claim_ids:
                failures.append(f'ssot risk row {risk_id} references unknown normalized claim {claim_ref!r}')
        traceability = row.get('traceability_refs', {})
        if not isinstance(traceability, Mapping):
            failures.append(f'ssot risk row {risk_id} has malformed traceability_refs')
            continue
        for claim_ref in traceability.get('claim_refs', []):
            if str(claim_ref) not in claim_ids:
                failures.append(f'ssot risk row {risk_id} references unknown claim {claim_ref!r}')
        for test_ref in traceability.get('test_refs', []):
            test_path = source_root / Path(str(test_ref).split('::', 1)[0])
            if not test_path.exists():
                failures.append(f'ssot risk row {risk_id} references missing test {test_ref!r}')
        for evidence_ref in traceability.get('evidence_refs', []):
            evidence_path = source_root / Path(str(evidence_ref))
            if not evidence_path.exists():
                failures.append(f'ssot risk row {risk_id} references missing evidence {evidence_ref!r}')

    for group_name, path in (
        ('interop_retention_bundles', source_root / 'docs/conformance/interop_retention.json'),
        ('performance_retention_bundles', source_root / 'docs/conformance/perf_retention.json'),
    ):
        retention_rows = _load_json_payload(path)
        if not isinstance(retention_rows, list):
            failures.append(f'{group_name} payload is malformed')
            continue
        for row in retention_rows:
            if not isinstance(row, Mapping):
                failures.append(f'{group_name} contains a malformed row')
                continue
            retained_path = source_root / Path(str(row.get('path', '')))
            if not retained_path.exists():
                failures.append(f'{group_name} references missing retained input {row.get("path")!r}')

    approved_legacy = list(inventory_payload.get('approved_legacy_files', []))
    detected_legacy = list(inventory_payload.get('detected_legacy_files', []))
    unexpected_legacy = list(inventory_payload.get('unexpected_legacy_files', []))
    if inventory_payload.get('forward_runner') != 'pytest':
        failures.append('legacy unittest inventory does not declare pytest as the forward runner')
    if unexpected_legacy:
        failures.append(f'legacy unittest inventory contains unexpected files: {sorted(str(item) for item in unexpected_legacy)}')
    if set(approved_legacy) != set(detected_legacy):
        failures.append('legacy unittest inventory detected files do not match the approved grandfathered inventory')

    return failures

__all__ = [name for name in globals() if not name.startswith('__')]

