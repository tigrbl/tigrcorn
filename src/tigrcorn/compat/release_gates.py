from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .interop_runner import InteropScenario, load_external_matrix

DEFAULT_BOUNDARY_PATH = Path('docs/review/conformance/certification_boundary.json')
DEFAULT_CORPUS_PATH = Path('docs/review/conformance/corpus.json')
DEFAULT_INDEPENDENT_MATRIX_PATH = Path('docs/review/conformance/external_matrix.release.json')
DEFAULT_SAME_STACK_MATRIX_PATH = Path('docs/review/conformance/external_matrix.same_stack_replay.json')
DEFAULT_TLS_WRAPPER_PATH = Path('src/tigrcorn/security/tls.py')
VALID_EVIDENCE_TIERS = ('local_conformance', 'same_stack_replay', 'independent_certification')
EVIDENCE_TIER_ORDER = {name: index for index, name in enumerate(VALID_EVIDENCE_TIERS, start=1)}


@dataclass(slots=True)
class ReleaseGateReport:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    rfc_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifact_status: dict[str, dict[str, Any]] = field(default_factory=dict)


class ReleaseGateError(RuntimeError):
    pass


def load_certification_boundary(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_conformance_corpus(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def evaluate_release_gates(
    source_root: str | Path,
    *,
    boundary_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
    independent_matrix_path: str | Path | None = None,
    same_stack_matrix_path: str | Path | None = None,
) -> ReleaseGateReport:
    source_root = Path(source_root)
    boundary_file = source_root / (Path(boundary_path) if boundary_path is not None else DEFAULT_BOUNDARY_PATH)
    corpus_file = source_root / (Path(corpus_path) if corpus_path is not None else DEFAULT_CORPUS_PATH)
    independent_file = source_root / (Path(independent_matrix_path) if independent_matrix_path is not None else DEFAULT_INDEPENDENT_MATRIX_PATH)
    same_stack_file = source_root / (Path(same_stack_matrix_path) if same_stack_matrix_path is not None else DEFAULT_SAME_STACK_MATRIX_PATH)

    failures: list[str] = []
    checked_files: list[str] = [str(boundary_file), str(corpus_file), str(independent_file), str(same_stack_file)]
    rfc_status: dict[str, dict[str, Any]] = {}
    artifact_status: dict[str, dict[str, Any]] = {}

    if not boundary_file.exists():
        failures.append(f'missing certification boundary file: {boundary_file}')
        return ReleaseGateReport(False, failures, checked_files, rfc_status, artifact_status)

    boundary = load_certification_boundary(boundary_file)
    canonical_doc = str(boundary.get('canonical_doc', 'docs/review/conformance/CERTIFICATION_BOUNDARY.md'))
    gates = dict(boundary.get('gates', {}))
    docs_to_check = [source_root / Path(item) for item in boundary.get('docs_that_must_reference_boundary', [])]
    checked_files.extend(str(path) for path in docs_to_check)

    if gates.get('require_docs_reference_canonical_boundary', False):
        failures.extend(_validate_boundary_references(canonical_doc=canonical_doc, docs_to_check=docs_to_check))

    corpus_payload: dict[str, Any] | None
    if gates.get('require_conformance_corpus', False):
        if not corpus_file.exists():
            failures.append(f'missing conformance corpus: {corpus_file}')
            corpus_payload = None
        else:
            corpus_payload = load_conformance_corpus(corpus_file)
    else:
        corpus_payload = load_conformance_corpus(corpus_file) if corpus_file.exists() else None

    independent_matrix = None
    if gates.get('require_independent_matrix', False):
        if not independent_file.exists():
            failures.append(f'missing independent certification matrix: {independent_file}')
        else:
            independent_matrix = load_external_matrix(independent_file)
            if not independent_matrix.scenarios:
                failures.append('independent certification matrix does not include any declared scenarios')
    elif independent_file.exists():
        independent_matrix = load_external_matrix(independent_file)

    same_stack_matrix = None
    if same_stack_file.exists():
        same_stack_matrix = load_external_matrix(same_stack_file)
        if any(scenario.evidence_tier != 'same_stack_replay' for scenario in same_stack_matrix.scenarios):
            failures.append('same-stack replay matrix contains a scenario outside the same_stack_replay tier')
    elif gates.get('require_docs_reference_canonical_boundary', False):
        failures.append(f'missing same-stack replay matrix: {same_stack_file}')

    if independent_matrix is not None:
        failures.extend(_evaluate_independent_matrix(independent_matrix.scenarios, gates=gates))

    if gates.get('require_package_owned_tls13_subsystem', False):
        tls_wrapper_path = source_root / DEFAULT_TLS_WRAPPER_PATH
        checked_files.append(str(tls_wrapper_path))
        if not tls_wrapper_path.exists():
            failures.append(f'missing TLS wrapper module: {tls_wrapper_path}')
        else:
            tls_wrapper_text = tls_wrapper_path.read_text(encoding='utf-8')
            if 'ssl.create_default_context' in tls_wrapper_text:
                failures.append(
                    'package-owned TLS 1.3 release gate failed because src/tigrcorn/security/tls.py still delegates TCP/TLS to ssl.create_default_context'
                )

    if gates.get('require_rfc_evidence_map', False) and corpus_payload is not None and independent_matrix is not None and same_stack_matrix is not None:
        failures.extend(
            _evaluate_rfc_evidence(
                source_root=source_root,
                boundary=boundary,
                corpus_payload=corpus_payload,
                independent_matrix_scenarios=independent_matrix.scenarios,
                same_stack_matrix_scenarios=same_stack_matrix.scenarios,
                checked_files=checked_files,
                rfc_status=rfc_status,
                artifact_status=artifact_status,
            )
        )

    return ReleaseGateReport(not failures, failures, checked_files, rfc_status, artifact_status)


def assert_release_ready(
    source_root: str | Path,
    *,
    boundary_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
    independent_matrix_path: str | Path | None = None,
    same_stack_matrix_path: str | Path | None = None,
) -> None:
    report = evaluate_release_gates(
        source_root,
        boundary_path=boundary_path,
        corpus_path=corpus_path,
        independent_matrix_path=independent_matrix_path,
        same_stack_matrix_path=same_stack_matrix_path,
    )
    if not report.passed:
        details = '\n'.join(f'- {item}' for item in report.failures)
        raise ReleaseGateError(f'release gates failed:\n{details}')


def _validate_boundary_references(*, canonical_doc: str, docs_to_check: list[Path]) -> list[str]:
    failures: list[str] = []
    for doc in docs_to_check:
        if not doc.exists():
            failures.append(f'missing documentation file: {doc}')
            continue
        text = doc.read_text(encoding='utf-8')
        if canonical_doc not in text:
            failures.append(f'{doc} does not reference the canonical certification boundary {canonical_doc}')
    return failures


def _evaluate_independent_matrix(scenarios: list[InteropScenario], *, gates: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    independent_scenarios = [scenario for scenario in scenarios if scenario.evidence_tier == 'independent_certification']
    if not independent_scenarios:
        failures.append('independent certification matrix does not contain any independent_certification scenarios')
        return failures

    for scenario in independent_scenarios:
        peer_kind = scenario.peer_process.provenance_kind
        if peer_kind == 'same_stack_fixture':
            failures.append(f'independent scenario {scenario.id} incorrectly uses a same_stack_fixture peer')
        if peer_kind not in {'third_party_library', 'third_party_binary'}:
            failures.append(f'independent scenario {scenario.id} is not backed by a true third-party peer: {peer_kind!r}')

    if gates.get('require_third_party_http3_request_response', False) and not _has_third_party_http3_request_response(independent_scenarios):
        failures.append('independent certification matrix does not declare a true third-party HTTP/3 request/response scenario')

    if gates.get('require_third_party_http3_websocket', False) and not _has_third_party_http3_websocket(independent_scenarios):
        failures.append('independent certification matrix does not declare a true third-party RFC 9220 WebSocket-over-HTTP/3 scenario')

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


def _load_preserved_artifacts(bundle_root: Path, *, artifact_status: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not bundle_root.exists():
        return {}
    index_path = bundle_root / 'index.json'
    if not index_path.exists():
        return {}
    payload = json.loads(index_path.read_text(encoding='utf-8'))
    scenarios: dict[str, dict[str, Any]] = {}
    for entry in payload.get('scenarios', []):
        scenario_id = str(entry.get('id'))
        if not scenario_id or scenario_id == 'None':
            continue
        result_path = bundle_root / scenario_id / 'result.json'
        passed = bool(entry.get('passed', False))
        if result_path.exists():
            try:
                result_payload = json.loads(result_path.read_text(encoding='utf-8'))
                passed = bool(result_payload.get('passed', passed))
            except Exception:
                pass
        status = {
            'artifact_dir': str(bundle_root / scenario_id),
            'passed': passed,
            'result_path': str(result_path),
            'exists': result_path.exists(),
        }
        scenarios[scenario_id] = status
        artifact_status[str(bundle_root / scenario_id)] = status
    return scenarios


def _has_third_party_http3_request_response(scenarios: list[InteropScenario]) -> bool:
    for scenario in scenarios:
        if scenario.protocol != 'http3':
            continue
        if scenario.peer_process.provenance_kind not in {'third_party_library', 'third_party_binary'}:
            continue
        rfcs = set(_scenario_rfcs(scenario))
        feature = scenario.feature.lower()
        if 'RFC 9220' in rfcs or 'websocket' in feature:
            continue
        if 'RFC 9114' not in rfcs and not any(token in feature for token in ('request', 'response', 'post', 'get', 'echo')):
            continue
        return True
    return False


def _has_third_party_http3_websocket(scenarios: list[InteropScenario]) -> bool:
    for scenario in scenarios:
        if scenario.protocol != 'http3':
            continue
        if scenario.peer_process.provenance_kind not in {'third_party_library', 'third_party_binary'}:
            continue
        rfcs = set(_scenario_rfcs(scenario))
        if 'RFC 9220' in rfcs or 'websocket' in scenario.feature.lower():
            return True
    return False


def _scenario_rfcs(scenario: InteropScenario) -> list[str]:
    metadata = scenario.metadata
    rfcs = metadata.get('rfc', []) if isinstance(metadata, dict) else []
    return [str(item) for item in rfcs]


def _index_corpus_vectors(corpus_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    vectors = corpus_payload.get('vectors', [])
    index: dict[str, dict[str, Any]] = {}
    for entry in vectors:
        if not isinstance(entry, dict) or 'name' not in entry:
            continue
        index[str(entry['name'])] = dict(entry)
    return index


def _normalize_rfc_from_corpus(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text.startswith('9110-connect'):
        return 'RFC 9110 §9.3.6'
    if text.startswith('9110-trailers'):
        return 'RFC 9110 §6.5'
    if text.startswith('9110-content-coding'):
        return 'RFC 9110 §8'
    if text.isdigit():
        return f'RFC {text}'
    return text


__all__ = [
    'DEFAULT_BOUNDARY_PATH',
    'DEFAULT_CORPUS_PATH',
    'DEFAULT_INDEPENDENT_MATRIX_PATH',
    'DEFAULT_SAME_STACK_MATRIX_PATH',
    'ReleaseGateError',
    'ReleaseGateReport',
    'assert_release_ready',
    'evaluate_release_gates',
    'load_certification_boundary',
    'load_conformance_corpus',
]
