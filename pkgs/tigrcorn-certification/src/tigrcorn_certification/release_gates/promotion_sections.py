from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *

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
    from ..perf_runner import load_performance_matrix, validate_performance_artifacts

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
def _split_required_performance_artifact_files(required_files: Iterable[str]) -> tuple[set[str], set[str]]:
    required = {str(item) for item in required_files}
    root_files = {'summary.json', 'index.json'} & required
    profile_files = required - {'index.json'}
    return root_files, profile_files
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

__all__ = [name for name in globals() if not name.startswith('__')]

