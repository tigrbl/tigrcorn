from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .interop_runner import InteropScenario, load_external_matrix

DEFAULT_BOUNDARY_PATH = Path('docs/review/conformance/certification_boundary.json')
DEFAULT_CORPUS_PATH = Path('docs/review/conformance/corpus.json')
DEFAULT_INDEPENDENT_MATRIX_PATH = Path('docs/review/conformance/external_matrix.release.json')
DEFAULT_SAME_STACK_MATRIX_PATH = Path('docs/review/conformance/external_matrix.same_stack_replay.json')
DEFAULT_STRICT_TARGET_BOUNDARY_PATH = Path('docs/review/conformance/certification_boundary.strict_target.json')
DEFAULT_PROMOTION_TARGET_PATH = Path('docs/review/conformance/promotion_gate.target.json')
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


@dataclass(slots=True)
class IndependentBundleReport:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    scenario_status: dict[str, dict[str, Any]] = field(default_factory=dict)


INDEPENDENT_BUNDLE_REQUIRED_ROOT_FILES = ('manifest.json', 'summary.json', 'index.json')
INDEPENDENT_BUNDLE_REQUIRED_SCENARIO_FILES = (
    'summary.json',
    'index.json',
    'result.json',
    'scenario.json',
    'command.json',
    'env.json',
    'versions.json',
    'wire_capture.json',
)


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
            failures.extend(_fail_closed_for_matrix_metadata(independent_matrix, matrix_name='independent certification matrix'))
            if not independent_matrix.scenarios:
                failures.append('independent certification matrix does not include any declared scenarios')
    elif independent_file.exists():
        independent_matrix = load_external_matrix(independent_file)

    same_stack_matrix = None
    if same_stack_file.exists():
        same_stack_matrix = load_external_matrix(same_stack_file)
        failures.extend(_fail_closed_for_matrix_metadata(same_stack_matrix, matrix_name='same-stack replay matrix'))
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
        failures.extend(_fail_closed_for_scenario_metadata(scenario))
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


def _fail_closed_for_matrix_metadata(matrix: Any, *, matrix_name: str) -> list[str]:
    failures: list[str] = []
    metadata = dict(getattr(matrix, 'metadata', {}) or {})
    pending_ids = metadata.get('pending_third_party_http3_scenarios', [])
    if isinstance(pending_ids, list) and pending_ids:
        failures.append(
            f'{matrix_name} declares blocked pending_third_party_http3_scenarios and therefore is not release-gate eligible: {sorted(str(item) for item in pending_ids)}'
        )
    blocked_ids = metadata.get('blocked_scenarios', [])
    if isinstance(blocked_ids, list) and blocked_ids:
        failures.append(
            f'{matrix_name} declares blocked_scenarios and therefore is not release-gate eligible: {sorted(str(item) for item in blocked_ids)}'
        )
    return failures


def _fail_closed_for_scenario_metadata(scenario: InteropScenario) -> list[str]:
    failures: list[str] = []
    metadata = dict(scenario.metadata or {})
    certification_status = str(metadata.get('certification_status', '')).strip().lower()
    blocked_statuses = {
        'blocked',
        'failed',
        'incomplete',
        'not_ready',
        'not_release_ready',
        'pending',
        'provisional',
    }
    if certification_status in blocked_statuses:
        failures.append(
            f'independent scenario {scenario.id} is blocked by certification_status={metadata.get("certification_status")!r}'
        )
    for key in ('blocked', 'pending'):
        if metadata.get(key) is True:
            failures.append(f'independent scenario {scenario.id} is blocked by metadata flag {key}=true')
    for key in ('blocked_reason', 'pending_reason', 'blocker'):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            failures.append(f'independent scenario {scenario.id} is blocked by metadata {key}={value!r}')
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


def validate_independent_certification_bundle(
    bundle_root: str | Path,
    *,
    required_scenarios: Iterable[str] | None = None,
    required_root_files: Iterable[str] = INDEPENDENT_BUNDLE_REQUIRED_ROOT_FILES,
    required_scenario_files: Iterable[str] = INDEPENDENT_BUNDLE_REQUIRED_SCENARIO_FILES,
) -> IndependentBundleReport:
    bundle_root = Path(bundle_root)
    failures: list[str] = []
    checked_files: list[str] = []
    scenario_status: dict[str, dict[str, Any]] = {}

    if not bundle_root.exists():
        failures.append(f'missing independent-certification bundle root: {bundle_root}')
        return IndependentBundleReport(False, failures, checked_files, scenario_status)

    for filename in required_root_files:
        checked_files.append(str(bundle_root / filename))
        if not (bundle_root / filename).exists():
            failures.append(f'missing bundle file: {bundle_root / filename}')

    if failures:
        return IndependentBundleReport(False, failures, checked_files, scenario_status)

    manifest = json.loads((bundle_root / 'manifest.json').read_text(encoding='utf-8'))
    summary = json.loads((bundle_root / 'summary.json').read_text(encoding='utf-8'))
    index = json.loads((bundle_root / 'index.json').read_text(encoding='utf-8'))

    if str(index.get('matrix_name', '')) != str(summary.get('matrix_name', '')):
        failures.append('bundle summary and index disagree on matrix_name')
    if str(index.get('commit_hash', '')) != str(summary.get('commit_hash', '')):
        failures.append('bundle summary and index disagree on commit_hash')
    if str(index.get('commit_hash', '')) != str(manifest.get('commit_hash', '')):
        failures.append('bundle manifest and index disagree on commit_hash')

    index_ids = {str(entry.get('id')) for entry in index.get('scenarios', []) if entry.get('id') is not None}
    summary_ids = {str(item) for item in summary.get('scenario_ids', []) if item is not None}
    if summary_ids and index_ids != summary_ids:
        failures.append('bundle summary scenario_ids do not match bundle index scenarios')

    if required_scenarios is not None:
        for scenario_id in required_scenarios:
            if scenario_id not in index_ids:
                failures.append(f'required proof scenario missing from bundle index: {scenario_id}')

    for entry in index.get('scenarios', []):
        scenario_id = str(entry.get('id', '')).strip()
        if not scenario_id:
            failures.append('bundle index contains a scenario entry without an id')
            continue
        scenario_dir = bundle_root / scenario_id
        checked_files.append(str(scenario_dir))
        if not scenario_dir.exists():
            failures.append(f'missing scenario directory: {scenario_dir}')
            continue
        status: dict[str, Any] = {
            'artifact_dir': str(scenario_dir),
            'required_files_present': True,
            'passed': bool(entry.get('passed', False)),
        }
        scenario_status[scenario_id] = status

        for filename in required_scenario_files:
            file_path = scenario_dir / filename
            checked_files.append(str(file_path))
            if not file_path.exists():
                failures.append(f'{scenario_id} missing required artifact file: {file_path}')
                status['required_files_present'] = False

        if not status['required_files_present']:
            continue

        result_payload = json.loads((scenario_dir / 'result.json').read_text(encoding='utf-8'))
        summary_payload = json.loads((scenario_dir / 'summary.json').read_text(encoding='utf-8'))
        scenario_index_payload = json.loads((scenario_dir / 'index.json').read_text(encoding='utf-8'))
        command_payload = json.loads((scenario_dir / 'command.json').read_text(encoding='utf-8'))
        env_payload = json.loads((scenario_dir / 'env.json').read_text(encoding='utf-8'))
        versions_payload = json.loads((scenario_dir / 'versions.json').read_text(encoding='utf-8'))
        wire_payload = json.loads((scenario_dir / 'wire_capture.json').read_text(encoding='utf-8'))

        status['passed'] = bool(result_payload.get('passed', False))
        if bool(entry.get('passed', False)) != bool(result_payload.get('passed', False)):
            failures.append(f'{scenario_id} bundle index passed flag disagrees with result.json')
        if bool(summary_payload.get('passed', False)) != bool(result_payload.get('passed', False)):
            failures.append(f'{scenario_id} summary.json passed flag disagrees with result.json')
        if bool(scenario_index_payload.get('passed', False)) != bool(result_payload.get('passed', False)):
            failures.append(f'{scenario_id} index.json passed flag disagrees with result.json')

        artifact_files = scenario_index_payload.get('artifact_files')
        if not isinstance(artifact_files, Mapping) or not artifact_files:
            failures.append(f'{scenario_id} index.json is missing a populated artifact_files inventory')
        else:
            for filename in required_scenario_files:
                metadata = artifact_files.get(filename)
                if not isinstance(metadata, Mapping) or not bool(metadata.get('exists', False)):
                    failures.append(f'{scenario_id} index.json does not record {filename} as an existing artifact')

        if 'sut' not in command_payload or 'peer' not in command_payload:
            failures.append(f'{scenario_id} command.json must contain sut and peer command records')
        if 'sut' not in env_payload or 'peer' not in env_payload:
            failures.append(f'{scenario_id} env.json must contain sut and peer environment records')
        if 'sut' not in versions_payload or 'peer' not in versions_payload:
            failures.append(f'{scenario_id} versions.json must contain sut and peer version records')
        if 'packet_trace' not in wire_payload or 'logs' not in wire_payload:
            failures.append(f'{scenario_id} wire_capture.json must contain packet_trace and logs sections')

    passed = not failures
    return IndependentBundleReport(passed, failures, checked_files, scenario_status)


def assert_independent_certification_bundle_ready(
    bundle_root: str | Path,
    *,
    required_scenarios: Iterable[str] | None = None,
    required_root_files: Iterable[str] = INDEPENDENT_BUNDLE_REQUIRED_ROOT_FILES,
    required_scenario_files: Iterable[str] = INDEPENDENT_BUNDLE_REQUIRED_SCENARIO_FILES,
) -> None:
    report = validate_independent_certification_bundle(
        bundle_root,
        required_scenarios=required_scenarios,
        required_root_files=required_root_files,
        required_scenario_files=required_scenario_files,
    )
    if report.passed:
        return
    raise ReleaseGateError('independent-certification bundle validation failed: ' + '; '.join(report.failures))


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


@dataclass(slots=True)
class PromotionSectionReport:
    name: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromotionTargetReport:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)
    authoritative_boundary: PromotionSectionReport | None = None
    strict_target_boundary: PromotionSectionReport | None = None
    flag_surface: PromotionSectionReport | None = None
    operator_surface: PromotionSectionReport | None = None
    performance: PromotionSectionReport | None = None
    documentation: PromotionSectionReport | None = None


class PromotionTargetError(RuntimeError):
    pass


def load_promotion_target(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def evaluate_promotion_target(
    source_root: str | Path,
    *,
    target_path: str | Path | None = None,
) -> PromotionTargetReport:
    source_root = Path(source_root)
    target_file = source_root / (Path(target_path) if target_path is not None else DEFAULT_PROMOTION_TARGET_PATH)
    checked_files: list[str] = [str(target_file)]
    if not target_file.exists():
        failure = f'missing promotion target file: {target_file}'
        return PromotionTargetReport(False, [failure], checked_files)

    target = load_promotion_target(target_file)

    authoritative_config = dict(target.get('authoritative_boundary', {}))
    authoritative_report = evaluate_release_gates(
        source_root,
        boundary_path=authoritative_config.get('boundary_path'),
        corpus_path=authoritative_config.get('corpus_path'),
        independent_matrix_path=authoritative_config.get('independent_matrix_path'),
        same_stack_matrix_path=authoritative_config.get('same_stack_matrix_path'),
    )
    authoritative_section = PromotionSectionReport(
        name='authoritative_boundary',
        passed=authoritative_report.passed,
        failures=list(authoritative_report.failures),
        checked_files=list(authoritative_report.checked_files),
        details={
            'boundary_path': authoritative_config.get('boundary_path', str(DEFAULT_BOUNDARY_PATH)),
            'required_rfcs': sorted(authoritative_report.rfc_status),
        },
    )

    strict_config = dict(target.get('strict_target_boundary', {}))
    strict_report = evaluate_release_gates(
        source_root,
        boundary_path=strict_config.get('boundary_path', str(DEFAULT_STRICT_TARGET_BOUNDARY_PATH)),
        corpus_path=strict_config.get('corpus_path'),
        independent_matrix_path=strict_config.get('independent_matrix_path'),
        same_stack_matrix_path=strict_config.get('same_stack_matrix_path'),
    )
    strict_section = PromotionSectionReport(
        name='strict_target_boundary',
        passed=strict_report.passed,
        failures=list(strict_report.failures),
        checked_files=list(strict_report.checked_files),
        details={
            'boundary_path': strict_config.get('boundary_path', str(DEFAULT_STRICT_TARGET_BOUNDARY_PATH)),
            'required_rfcs': sorted(strict_report.rfc_status),
        },
    )

    flag_section = _evaluate_flag_contract_target(source_root, dict(target.get('flag_surface', {})))
    operator_section = _evaluate_operator_surface_target(source_root, dict(target.get('operator_surface', {})))
    performance_section = _evaluate_performance_target(source_root, dict(target.get('performance', {})))
    documentation_section = _evaluate_documentation_claim_consistency(source_root, dict(target.get('documentation', {})))

    sections = [
        authoritative_section,
        strict_section,
        flag_section,
        operator_section,
        performance_section,
        documentation_section,
    ]

    failures: list[str] = []
    for section in sections:
        checked_files.extend(section.checked_files)
        failures.extend(f'[{section.name}] {failure}' for failure in section.failures)

    checked_files = list(dict.fromkeys(checked_files))
    return PromotionTargetReport(
        passed=all(section.passed for section in sections),
        failures=failures,
        checked_files=checked_files,
        authoritative_boundary=authoritative_section,
        strict_target_boundary=strict_section,
        flag_surface=flag_section,
        operator_surface=operator_section,
        performance=performance_section,
        documentation=documentation_section,
    )


def assert_promotion_target_ready(
    source_root: str | Path,
    *,
    target_path: str | Path | None = None,
) -> None:
    report = evaluate_promotion_target(source_root, target_path=target_path)
    if not report.passed:
        details = '\n'.join(f'- {item}' for item in report.failures)
        raise PromotionTargetError(f'promotion target failed:\n{details}')


def _evaluate_flag_contract_target(source_root: Path, config: Mapping[str, Any]) -> PromotionSectionReport:
    contracts_file = source_root / Path(str(config.get('contracts_path', 'docs/review/conformance/flag_contracts.json')))
    covering_file = source_root / Path(str(config.get('covering_array_path', 'docs/review/conformance/flag_covering_array.json')))
    checked_files = [str(contracts_file), str(covering_file), str(source_root / 'src/tigrcorn/cli.py')]
    failures: list[str] = []
    details: dict[str, Any] = {}

    if not contracts_file.exists():
        failures.append(f'missing flag contracts file: {contracts_file}')
        return PromotionSectionReport('flag_surface', False, failures, checked_files, details)
    if not covering_file.exists():
        failures.append(f'missing flag covering-array file: {covering_file}')
        return PromotionSectionReport('flag_surface', False, failures, checked_files, details)

    contracts_payload = json.loads(contracts_file.read_text(encoding='utf-8'))
    covering_payload = json.loads(covering_file.read_text(encoding='utf-8'))
    public_flags = _load_public_parser_flags()
    required_fields = [str(item) for item in config.get('required_contract_fields', [])]

    contracts = list(contracts_payload.get('contracts', []))
    if contracts_payload.get('contract_mode') != 'one_row_per_concrete_public_flag':
        failures.append('flag contracts must declare contract_mode=one_row_per_concrete_public_flag')

    seen: dict[str, int] = {}
    non_ready: list[str] = []
    runtime_gaps: list[str] = []
    for row in contracts:
        for field_name in required_fields:
            if field_name not in row:
                failures.append(f'flag contract is missing required field {field_name!r}: {row!r}')
        flag_strings = row.get('flag_strings', [])
        if not isinstance(flag_strings, list) or len(flag_strings) != 1 or not isinstance(flag_strings[0], str):
            failures.append(f'flag contract must contain exactly one concrete flag string: {row!r}')
            continue
        flag = flag_strings[0]
        seen[flag] = seen.get(flag, 0) + 1
        status = dict(row.get('status', {})) if isinstance(row.get('status'), Mapping) else {}
        if not bool(status.get('contract_defined', False)):
            failures.append(f'{flag} contract is not marked contract_defined=true')
        if not bool(status.get('promotion_ready', False)):
            non_ready.append(flag)
        runtime_state = str(status.get('current_runtime_state', 'unknown'))
        if runtime_state in {'parse_only', 'partially_wired', 'runtime_gap'}:
            runtime_gaps.append(flag)

    public_flag_set = set(public_flags)
    documented_flag_set = set(seen)
    missing_contracts = sorted(public_flag_set - documented_flag_set)
    extra_contracts = sorted(documented_flag_set - public_flag_set)
    duplicate_contracts = sorted(flag for flag, count in seen.items() if count > 1)
    if missing_contracts:
        failures.append(f'flag contracts are missing concrete public flags: {missing_contracts}')
    if extra_contracts:
        failures.append(f'flag contracts declare non-public flags: {extra_contracts}')
    if duplicate_contracts:
        failures.append(f'flag contracts declare duplicate rows: {duplicate_contracts}')
    expected_public_count = int(contracts_payload.get('public_flag_string_count', len(public_flag_set)))
    if expected_public_count != len(public_flag_set):
        failures.append(
            f'flag contracts public_flag_string_count={expected_public_count} does not match parser public flag count={len(public_flag_set)}'
        )
    if len(contracts) != len(public_flag_set):
        failures.append(
            f'flag contracts contain {len(contracts)} rows but the parser exposes {len(public_flag_set)} concrete public flags'
        )

    cases = list(covering_payload.get('cases', []))
    covered_flags: set[str] = set()
    for case in cases:
        for dimension in case.get('dimensions', []):
            if not isinstance(dimension, Mapping):
                continue
            flag = dimension.get('flag')
            if isinstance(flag, str):
                covered_flags.add(flag)
    missing_coverage = sorted(public_flag_set - covered_flags)
    if missing_coverage:
        failures.append(f'flag covering array does not exercise every public flag: {missing_coverage}')

    declared_hazard_clusters = {
        str(cluster.get('cluster_id'))
        for cluster in covering_payload.get('hazard_clusters', [])
        if isinstance(cluster, Mapping) and cluster.get('cluster_id')
    }
    for cluster_id in [str(item) for item in config.get('required_hazard_clusters', [])]:
        if cluster_id not in declared_hazard_clusters:
            failures.append(f'flag covering array is missing required hazard cluster {cluster_id!r}')

    if non_ready:
        failures.append(
            'flag surface still has non-promotion-ready contracts: ' + ', '.join(sorted(non_ready))
        )

    details.update(
        {
            'public_flag_count': len(public_flag_set),
            'contract_row_count': len(contracts),
            'promotion_ready_count': len(contracts) - len(non_ready),
            'runtime_gap_flags': sorted(runtime_gaps),
            'missing_contracts': missing_contracts,
            'missing_coverage': missing_coverage,
            'hazard_cluster_count': len(declared_hazard_clusters),
        }
    )
    return PromotionSectionReport('flag_surface', not failures, failures, checked_files, details)



def _evaluate_operator_surface_target(source_root: Path, config: Mapping[str, Any]) -> PromotionSectionReport:
    index_file = source_root / Path(str(config.get('bundle_index', 'docs/review/conformance/releases/0.3.7/release-0.3.7/tigrcorn-operator-surface-certification-bundle/index.json')))
    checked_files = [str(index_file)]
    failures: list[str] = []
    details: dict[str, Any] = {}
    if not index_file.exists():
        failures.append(f'missing operator-surface bundle index: {index_file}')
        return PromotionSectionReport('operator_surface', False, failures, checked_files, details)
    payload = json.loads(index_file.read_text(encoding='utf-8'))
    implemented = dict(payload.get('implemented', {}))
    required_keys = [str(item) for item in config.get('required_implemented_keys', [])]
    if not bool(payload.get('release_gate_eligible', False)):
        failures.append('operator-surface certification bundle is not release_gate_eligible')
    missing_keys = [key for key in required_keys if key not in implemented]
    false_keys = [key for key in required_keys if implemented.get(key) is not True]
    if missing_keys:
        failures.append(f'operator-surface bundle is missing required implementation keys: {missing_keys}')
    if false_keys:
        failures.append(f'operator-surface bundle contains non-green required implementation keys: {false_keys}')
    details.update(
        {
            'implemented_count': int(payload.get('implemented_count', len([item for item in implemented.values() if item]))),
            'required_implemented_keys': required_keys,
            'implemented_keys': sorted(implemented),
        }
    )
    return PromotionSectionReport('operator_surface', not failures, failures, checked_files, details)



def _evaluate_performance_target(source_root: Path, config: Mapping[str, Any]) -> PromotionSectionReport:
    from .perf_runner import load_performance_matrix, validate_performance_artifacts

    matrix_path = Path(str(config.get('matrix_path', 'docs/review/performance/performance_matrix.json')))
    slos_path = Path(str(config.get('slos_path', 'docs/review/performance/performance_slos.json')))
    current_artifact_root = Path(str(config.get('current_artifact_root', 'docs/review/performance/artifacts/phase6_current_release')))
    baseline_artifact_root = Path(str(config.get('baseline_artifact_root', 'docs/review/performance/artifacts/phase6_reference_baseline')))
    checked_files = [str(source_root / matrix_path), str(source_root / slos_path), str(source_root / current_artifact_root)]
    failures: list[str] = []
    details: dict[str, Any] = {}

    if not (source_root / matrix_path).exists():
        failures.append(f'missing performance matrix file: {source_root / matrix_path}')
        return PromotionSectionReport('performance', False, failures, checked_files, details)
    if not (source_root / slos_path).exists():
        failures.append(f'missing performance SLO target file: {source_root / slos_path}')
        return PromotionSectionReport('performance', False, failures, checked_files, details)

    matrix = load_performance_matrix(source_root / matrix_path)
    slos_payload = json.loads((source_root / slos_path).read_text(encoding='utf-8'))
    artifact_failures = validate_performance_artifacts(
        source_root,
        matrix_path=matrix_path,
        artifact_root=current_artifact_root,
        baseline_root=baseline_artifact_root,
        require_relative_regression=bool(config.get('require_relative_regression', False)),
    )
    failures.extend(artifact_failures)

    required_metric_keys = {str(item) for item in slos_payload.get('required_metric_keys', [])}
    required_threshold_keys = {str(item) for item in slos_payload.get('required_threshold_keys', [])}
    required_relative_budget_keys = {str(item) for item in slos_payload.get('required_relative_regression_budget_keys', [])}
    required_artifact_files = {str(item) for item in slos_payload.get('required_artifact_files', [])}
    required_matrix_lanes = {str(item) for item in slos_payload.get('required_matrix_lanes', [])}
    promotion_requirements = dict(slos_payload.get('promotion_requirements', {}))

    require_full_declared_strict_contract = bool(config.get('require_full_declared_strict_contract', False))
    require_artifact_files = require_full_declared_strict_contract or bool(config.get('require_required_artifact_files', False))
    require_matrix_lanes = require_full_declared_strict_contract or bool(config.get('require_required_matrix_lanes', False))
    require_certification_platforms = (
        require_full_declared_strict_contract
        or bool(config.get('require_certification_platform_declarations', False))
        or bool(promotion_requirements.get('require_certification_platforms', False))
    )
    require_documented_slos_per_profile = (
        require_full_declared_strict_contract
        or bool(config.get('require_documented_slos_per_profile', False))
        or bool(promotion_requirements.get('require_documented_slos_per_profile', False))
    )
    require_correctness_for_rfc_targets = (
        require_full_declared_strict_contract
        or bool(config.get('require_correctness_for_rfc_profiles', False))
        or bool(promotion_requirements.get('require_correctness_under_load_for_rfc_targets', False))
    )
    require_live_listener_metadata = (
        require_full_declared_strict_contract
        or bool(config.get('require_live_listener_metadata_for_end_to_end_profiles', False))
        or bool(promotion_requirements.get('require_end_to_end_live_listener_profiles', False))
    )

    observed_metric_keys = _load_performance_metric_keys(source_root / current_artifact_root, [profile.profile_id for profile in matrix.profiles])
    declared_threshold_keys = {key for profile in matrix.profiles for key in profile.thresholds}
    declared_relative_keys = {key for profile in matrix.profiles for key in profile.relative_regression_budget}

    missing_metric_keys = sorted(required_metric_keys - observed_metric_keys)
    missing_threshold_keys = sorted(required_threshold_keys - declared_threshold_keys)
    missing_relative_keys = sorted(required_relative_budget_keys - declared_relative_keys)
    if missing_metric_keys:
        failures.append(f'performance artifacts are missing required SLO metric keys: {missing_metric_keys}')
    if missing_threshold_keys:
        failures.append(f'performance matrix is missing required absolute threshold keys: {missing_threshold_keys}')
    if missing_relative_keys:
        failures.append(f'performance matrix is missing required relative regression budget keys: {missing_relative_keys}')

    artifact_root_path = source_root / current_artifact_root
    root_summary_path = artifact_root_path / 'summary.json'
    root_index_path = artifact_root_path / 'index.json'
    root_summary = _load_json_payload(root_summary_path) if root_summary_path.exists() else {}
    root_index = _load_json_payload(root_index_path) if root_index_path.exists() else {}

    if require_artifact_files:
        required_root_files, required_profile_files = _split_required_performance_artifact_files(required_artifact_files)
        missing_root_files = sorted(filename for filename in required_root_files if not (artifact_root_path / filename).exists())
        if missing_root_files:
            failures.append(f'performance artifact root is missing required files: {missing_root_files}')
        for profile in matrix.profiles:
            profile_dir = artifact_root_path / profile.profile_id
            missing_profile_files = sorted(filename for filename in required_profile_files if not (profile_dir / filename).exists())
            if missing_profile_files:
                failures.append(f'{profile.profile_id} performance artifact directory is missing required files: {missing_profile_files}')

    if require_matrix_lanes:
        declared_lanes = {profile.lane for profile in matrix.profiles}
        missing_lanes = sorted(required_matrix_lanes - declared_lanes)
        if missing_lanes:
            failures.append(f'performance matrix is missing required lanes: {missing_lanes}')
        lane_counts = root_summary.get('lane_counts', {}) if isinstance(root_summary, Mapping) else {}
        lane_count_keys = {str(key) for key in lane_counts} if isinstance(lane_counts, Mapping) else set()
        missing_lane_counts = sorted(required_matrix_lanes - lane_count_keys)
        if missing_lane_counts:
            failures.append(f'performance artifact summary is missing required lane counts: {missing_lane_counts}')
        for lane in sorted(required_matrix_lanes & lane_count_keys):
            try:
                if int(lane_counts[lane]) <= 0:
                    failures.append(f'performance artifact summary declares non-positive count for required lane {lane!r}')
            except Exception:
                failures.append(f'performance artifact summary carries a non-integer lane count for required lane {lane!r}')

    matrix_platforms = [str(item) for item in matrix.metadata.get('certification_platforms', [])]
    if require_certification_platforms and not matrix_platforms:
        failures.append('performance matrix metadata is missing certification_platforms declarations')
    root_certification_platform = ''
    if isinstance(root_summary, Mapping):
        if root_summary.get('certification_platform') is not None:
            root_certification_platform = str(root_summary.get('certification_platform', ''))
        elif root_summary.get('certification_platforms'):
            platforms = root_summary.get('certification_platforms')
            if isinstance(platforms, list) and platforms:
                root_certification_platform = str(platforms[0])
    if require_certification_platforms and not root_certification_platform:
        failures.append('performance artifact summary is missing certification platform declarations')

    if require_matrix_lanes and isinstance(root_index, Mapping):
        summary_profiles = root_index.get('profiles', []) or root_index.get('scenarios', []) or []
        details['artifact_profile_entry_count'] = len(summary_profiles) if isinstance(summary_profiles, list) else 0

    profile_failures: dict[str, list[str]] = {}
    for profile in matrix.profiles:
        profile_dir = artifact_root_path / profile.profile_id
        result_payload = _load_json_payload(profile_dir / 'result.json') if (profile_dir / 'result.json').exists() else {}
        summary_payload = _load_json_payload(profile_dir / 'summary.json') if (profile_dir / 'summary.json').exists() else {}
        command_payload = _load_json_payload(profile_dir / 'command.json') if (profile_dir / 'command.json').exists() else {}
        env_payload = _load_json_payload(profile_dir / 'env.json') if (profile_dir / 'env.json').exists() else {}
        correctness_payload = _load_json_payload(profile_dir / 'correctness.json') if (profile_dir / 'correctness.json').exists() else {}

        current_profile_failures: list[str] = []

        if require_documented_slos_per_profile:
            if not str(profile.description).strip():
                current_profile_failures.append('missing non-empty profile description for documented SLO coverage')
            missing_profile_threshold_keys = sorted(required_threshold_keys - set(profile.thresholds))
            if missing_profile_threshold_keys:
                current_profile_failures.append(f'missing required threshold keys: {missing_profile_threshold_keys}')
            missing_profile_relative_keys = sorted(required_relative_budget_keys - set(profile.relative_regression_budget))
            if missing_profile_relative_keys:
                current_profile_failures.append(f'missing required relative regression budget keys: {missing_profile_relative_keys}')

        if require_certification_platforms:
            if not profile.certification_platforms:
                current_profile_failures.append('missing profile certification_platforms declarations in matrix')
            if not result_payload.get('certification_platforms'):
                current_profile_failures.append('missing result.json certification_platforms declarations')
            if not summary_payload.get('certification_platforms'):
                current_profile_failures.append('missing summary.json certification_platforms declarations')
            if not command_payload.get('certification_platforms'):
                current_profile_failures.append('missing command.json certification_platforms declarations')
            if not env_payload.get('certification_platform'):
                current_profile_failures.append('missing env.json certification_platform declaration')
            if not env_payload.get('matrix_declared_platforms'):
                current_profile_failures.append('missing env.json matrix_declared_platforms declaration')

        if require_correctness_for_rfc_targets and profile.rfc_targets:
            if not profile.correctness_required:
                current_profile_failures.append('RFC-scoped profile is not marked correctness_required=true in the matrix')
            checks = correctness_payload.get('checks', {}) if isinstance(correctness_payload, Mapping) else {}
            if not bool(correctness_payload.get('required', False)):
                current_profile_failures.append('correctness.json is not marked required=true for an RFC-scoped profile')
            if not bool(correctness_payload.get('passed', False)):
                current_profile_failures.append('correctness.json does not record passed=true for an RFC-scoped profile')
            if not isinstance(checks, Mapping) or not checks:
                current_profile_failures.append('correctness.json is missing correctness checks for an RFC-scoped profile')

        if require_live_listener_metadata and profile.lane == 'end_to_end_release':
            if not profile.live_listener_required:
                current_profile_failures.append('end_to_end_release profile is not marked live_listener_required=true in the matrix')
            for filename, payload in [
                ('result.json', result_payload),
                ('summary.json', summary_payload),
                ('command.json', command_payload),
                ('correctness.json', correctness_payload),
            ]:
                if payload and payload.get('live_listener_required') is not True:
                    current_profile_failures.append(f'{filename} does not preserve live_listener_required=true for an end_to_end_release profile')
                if payload and str(payload.get('lane', '')) != 'end_to_end_release':
                    current_profile_failures.append(f'{filename} does not preserve lane="end_to_end_release" for an end_to_end_release profile')

        if current_profile_failures:
            profile_failures[profile.profile_id] = list(current_profile_failures)
            failures.extend(f'{profile.profile_id} {message}' for message in current_profile_failures)

    details.update(
        {
            'profile_count': len(matrix.profiles),
            'required_metric_keys': sorted(required_metric_keys),
            'observed_metric_keys': sorted(observed_metric_keys),
            'missing_metric_keys': missing_metric_keys,
            'missing_threshold_keys': missing_threshold_keys,
            'missing_relative_budget_keys': missing_relative_keys,
            'required_artifact_files': sorted(required_artifact_files),
            'required_matrix_lanes': sorted(required_matrix_lanes),
            'certification_platforms': matrix_platforms,
            'profile_failures': profile_failures,
            'require_full_declared_strict_contract': require_full_declared_strict_contract,
            'require_certification_platforms': require_certification_platforms,
            'require_documented_slos_per_profile': require_documented_slos_per_profile,
            'require_correctness_for_rfc_targets': require_correctness_for_rfc_targets,
            'require_live_listener_metadata': require_live_listener_metadata,
        }
    )
    return PromotionSectionReport('performance', not failures, failures, checked_files, details)



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






def _split_required_performance_artifact_files(required_files: Iterable[str]) -> tuple[set[str], set[str]]:
    required = {str(item) for item in required_files}
    root_files = {'summary.json', 'index.json'} & required
    profile_files = required - {'index.json'}
    return root_files, profile_files



def _load_json_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def _load_public_parser_flags() -> dict[str, dict[str, Any]]:
    import argparse

    from tigrcorn.cli import build_parser

    parser = build_parser()
    public_flags: dict[str, dict[str, Any]] = {}
    for group in parser._action_groups:
        title = getattr(group, 'title', None)
        for action in getattr(group, '_group_actions', []):
            if isinstance(action, argparse._HelpAction):
                continue
            if action.help == argparse.SUPPRESS:
                continue
            for flag in action.option_strings:
                if not flag.startswith('--'):
                    continue
                public_flags[flag] = {
                    'dest': action.dest,
                    'group': title,
                    'choices': list(action.choices) if action.choices is not None else [],
                    'nargs': action.nargs,
                    'default': action.default,
                }
    return public_flags



def _load_performance_metric_keys(artifact_root: Path, profile_ids: list[str]) -> set[str]:
    metric_keys: set[str] = set()
    for profile_id in profile_ids:
        result_file = artifact_root / profile_id / 'result.json'
        if not result_file.exists():
            continue
        payload = json.loads(result_file.read_text(encoding='utf-8'))
        metrics = payload.get('metrics', {})
        if isinstance(metrics, Mapping):
            metric_keys.update(str(key) for key in metrics)
    return metric_keys


__all__ = [
    'DEFAULT_BOUNDARY_PATH',
    'DEFAULT_CORPUS_PATH',
    'DEFAULT_INDEPENDENT_MATRIX_PATH',
    'DEFAULT_SAME_STACK_MATRIX_PATH',
    'DEFAULT_STRICT_TARGET_BOUNDARY_PATH',
    'DEFAULT_PROMOTION_TARGET_PATH',
    'PromotionSectionReport',
    'PromotionTargetError',
    'PromotionTargetReport',
    'ReleaseGateError',
    'ReleaseGateReport',
    'assert_promotion_target_ready',
    'assert_release_ready',
    'evaluate_promotion_target',
    'evaluate_release_gates',
    'load_certification_boundary',
    'load_conformance_corpus',
    'load_promotion_target',
]
