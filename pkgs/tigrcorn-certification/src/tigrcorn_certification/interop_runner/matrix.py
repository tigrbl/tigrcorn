from __future__ import annotations

from .imports import *
from .models import *
from .helpers import *
from .environment import *

def load_external_matrix(path: str | Path) -> InteropMatrix:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    matrix_payload = payload.get('matrix', payload)
    metadata = dict(matrix_payload.get('metadata', {}))
    default_evidence_tier = str(metadata.get('evidence_tier', 'mixed'))
    scenarios = [_load_scenario(entry, default_evidence_tier=default_evidence_tier) for entry in matrix_payload.get('scenarios', [])]
    return InteropMatrix(
        name=matrix_payload['name'],
        scenarios=scenarios,
        metadata=metadata,
    )



def summarize_matrix_dimensions(matrix: InteropMatrix) -> dict[str, list[Any]]:
    keys = [
        'protocol', 'role', 'feature', 'peer', 'cipher_group', 'ip_family', 'retry', 'resumption', 'zero_rtt', 'key_update', 'migration', 'goaway', 'qpack_blocking', 'evidence_tier'
    ]
    dimensions: dict[str, set[Any]] = {key: set() for key in keys}
    for scenario in matrix.scenarios:
        for key, value in scenario.dimensions.items():
            dimensions[key].add(value)
    return {key: sorted(values) for key, values in dimensions.items()}
def _load_scenario(entry: dict[str, Any], *, default_evidence_tier: str = 'mixed') -> InteropScenario:
    evidence_tier = str(entry.get('evidence_tier', default_evidence_tier))
    if evidence_tier not in VALID_EVIDENCE_TIERS:
        raise InteropRunnerError(f'invalid evidence_tier: {evidence_tier!r}')
    scenario = InteropScenario(
        id=entry['id'],
        protocol=entry['protocol'],
        role=entry['role'],
        feature=entry['feature'],
        peer=entry['peer'],
        sut=_load_process_spec(entry['sut']),
        peer_process=_load_process_spec(entry['peer_process']),
        assertions=[dict(item) for item in entry.get('assertions', [])],
        transport=entry.get('transport'),
        ip_family=entry.get('ip_family', 'ipv4'),
        cipher_group=entry.get('cipher_group'),
        retry=bool(entry.get('retry', False)),
        resumption=bool(entry.get('resumption', False)),
        zero_rtt=bool(entry.get('zero_rtt', False)),
        key_update=bool(entry.get('key_update', False)),
        migration=bool(entry.get('migration', False)),
        goaway=bool(entry.get('goaway', False)),
        qpack_blocking=bool(entry.get('qpack_blocking', False)),
        capture=dict(entry.get('capture', {})),
        metadata=dict(entry.get('metadata', {})),
        evidence_tier=evidence_tier,
        enabled=bool(entry.get('enabled', True)),
    )
    _validate_scenario_provenance(scenario)
    return scenario



def _load_process_spec(entry: dict[str, Any]) -> InteropProcessSpec:
    command = entry.get('command')
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise InteropRunnerError('process command must be a list of strings')
    version_command = entry.get('version_command')
    if version_command is not None and (not isinstance(version_command, list) or not all(isinstance(item, str) for item in version_command)):
        raise InteropRunnerError('version_command must be a list of strings when provided')
    spec = InteropProcessSpec(
        name=entry['name'],
        adapter=entry.get('adapter', 'subprocess'),
        role=entry['role'],
        command=list(command),
        env={str(key): str(value) for key, value in dict(entry.get('env', {})).items()},
        cwd=entry.get('cwd'),
        ready_pattern=entry.get('ready_pattern'),
        ready_timeout=float(entry.get('ready_timeout', DEFAULT_READY_TIMEOUT)),
        run_timeout=float(entry.get('run_timeout', DEFAULT_RUN_TIMEOUT)),
        version_command=list(version_command) if version_command is not None else None,
        image=entry.get('image'),
        enabled=bool(entry.get('enabled', True)),
        metadata=dict(entry.get('metadata', {})),
        provenance_kind=str(entry.get('provenance_kind', 'unspecified')),
        implementation_source=entry.get('implementation_source'),
        implementation_identity=entry.get('implementation_identity'),
        implementation_version=entry.get('implementation_version'),
    )
    _validate_process_provenance(spec)
    return spec
def _matrix_to_json(matrix: InteropMatrix) -> dict[str, Any]:
    return {
        'name': matrix.name,
        'metadata': matrix.metadata,
        'scenarios': [
            {
                'id': scenario.id,
                'protocol': scenario.protocol,
                'role': scenario.role,
                'feature': scenario.feature,
                'peer': scenario.peer,
                'transport': scenario.transport,
                'ip_family': scenario.ip_family,
                'cipher_group': scenario.cipher_group,
                'retry': scenario.retry,
                'resumption': scenario.resumption,
                'zero_rtt': scenario.zero_rtt,
                'key_update': scenario.key_update,
                'migration': scenario.migration,
                'goaway': scenario.goaway,
                'qpack_blocking': scenario.qpack_blocking,
                'capture': scenario.capture,
                'metadata': scenario.metadata,
                'evidence_tier': scenario.evidence_tier,
                'assertions': scenario.assertions,
                'sut': _spec_to_json(scenario.sut),
                'peer_process': _spec_to_json(scenario.peer_process),
                'enabled': scenario.enabled,
            }
            for scenario in matrix.scenarios
        ],
    }



def _spec_to_json(spec: InteropProcessSpec) -> dict[str, Any]:
    return {
        'name': spec.name,
        'adapter': spec.adapter,
        'role': spec.role,
        'command': spec.command,
        'env': spec.env,
        'cwd': spec.cwd,
        'ready_pattern': spec.ready_pattern,
        'ready_timeout': spec.ready_timeout,
        'run_timeout': spec.run_timeout,
        'version_command': spec.version_command,
        'image': spec.image,
        'enabled': spec.enabled,
        'metadata': spec.metadata,
        'provenance_kind': spec.provenance_kind,
        'implementation_source': spec.implementation_source,
        'implementation_identity': spec.implementation_identity,
        'implementation_version': spec.implementation_version,
    }

__all__ = [name for name in globals() if not name.startswith('__')]
