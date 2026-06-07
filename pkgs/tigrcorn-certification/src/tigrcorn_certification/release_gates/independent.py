from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *

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

__all__ = [name for name in globals() if not name.startswith('__')]

