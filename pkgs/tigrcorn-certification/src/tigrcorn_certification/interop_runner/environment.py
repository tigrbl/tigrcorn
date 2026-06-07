from __future__ import annotations

from .imports import *
from .models import *
from .helpers import *

def detect_source_revision(source_root: str | Path) -> str:
    env_commit = os.environ.get('TIGRCORN_COMMIT_HASH') or os.environ.get('GIT_COMMIT')
    if env_commit:
        return env_commit
    try:
        completed = subprocess.run(
            ['git', '-C', str(Path(source_root)), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
    except Exception:
        pass
    return f'tree-{hash_source_tree(source_root)[:16]}'



def build_environment_manifest(source_root: str | Path, *, commit_hash: str | None = None) -> dict[str, Any]:
    source_root = Path(source_root)
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'python': {
            'version': platform.python_version(),
            'implementation': platform.python_implementation(),
            'executable': os.sys.executable,
        },
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'platform': platform.platform(),
        },
        'tigrcorn': {
            'version': __version__,
            'commit_hash': commit_hash or detect_source_revision(source_root),
            'source_tree_sha256': hash_source_tree(source_root),
        },
        'tools': {
            'git': _probe_command(['git', '--version']),
            'docker': _probe_command(['docker', '--version']),
            'curl': _probe_command(['curl', '--version']),
            'openssl': _probe_command(['openssl', 'version']),
        },
    }



def hash_source_tree(source_root: str | Path) -> str:
    source_root = Path(source_root)
    entries: list[tuple[str, str]] = []
    skipped_prefixes = (
        ('docs', 'review', 'conformance', 'releases'),
        ('.artifacts',),
        ('.tmp',),
        ('dist',),
    )
    for root, _dirs, filenames in os.walk(source_root):
        root_path = Path(root)
        if '.git' in root_path.parts or '__pycache__' in root_path.parts:
            continue
        relative_parts = root_path.relative_to(source_root).parts if root_path != source_root else ()
        if any(part.startswith('tmp') for part in relative_parts):
            continue
        if any(relative_parts[:len(prefix)] == prefix for prefix in skipped_prefixes):
            continue
        for filename in sorted(filenames):
            path = root_path / filename
            if path.suffix in {'.pyc', '.pyo'} or not path.is_file():
                continue
            entries.append((str(path.relative_to(source_root)), _sha256_path(path)))
    return _sha256_bytes(json.dumps(entries, separators=(',', ':')).encode('utf-8'))
def _validate_process_provenance(spec: InteropProcessSpec) -> None:
    if spec.provenance_kind not in VALID_PROVENANCE_KINDS:
        raise InteropRunnerError(f'invalid provenance_kind for {spec.name}: {spec.provenance_kind!r}')
    if spec.provenance_kind != 'unspecified' and not spec.implementation_identity:
        raise InteropRunnerError(f'implementation_identity is required for {spec.name} when provenance_kind is {spec.provenance_kind!r}')
    if spec.provenance_kind in {'third_party_library', 'third_party_binary'} and not spec.implementation_source:
        raise InteropRunnerError(f'implementation_source is required for third-party peer {spec.name}')



def _validate_scenario_provenance(scenario: InteropScenario) -> None:
    if scenario.evidence_tier not in VALID_EVIDENCE_TIERS:
        raise InteropRunnerError(f'invalid evidence_tier for {scenario.id}: {scenario.evidence_tier!r}')
    if scenario.evidence_tier == 'independent_certification':
        peer_kind = scenario.peer_process.provenance_kind
        if peer_kind not in {'third_party_library', 'third_party_binary'}:
            raise InteropRunnerError(
                f'independent_certification scenario {scenario.id} requires a third-party peer, not {peer_kind!r}'
            )
        if not scenario.peer_process.implementation_identity or not scenario.peer_process.implementation_source:
            raise InteropRunnerError(
                f'independent_certification scenario {scenario.id} requires peer implementation_identity and implementation_source'
            )



def _build_provenance_payload(spec: InteropProcessSpec, version: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'kind': spec.provenance_kind,
        'implementation_source': spec.implementation_source,
        'implementation_identity': spec.implementation_identity,
        'implementation_version': spec.implementation_version,
    }
    if version:
        observed = version.get('version_stdout') or version.get('stdout')
        if observed:
            payload['observed_version_output'] = observed
    return payload


def _instantiate_adapter(name: str) -> BasePeerAdapter:
    try:
        return _ADAPTERS[name]()
    except KeyError as exc:
        raise InteropRunnerError(f'unknown interop adapter: {name}') from exc
def _materialize_process_spec(spec: InteropProcessSpec, context: Mapping[str, str]) -> InteropProcessSpec:
    return InteropProcessSpec(
        name=_apply_template(spec.name, context),
        adapter=spec.adapter,
        role=spec.role,
        command=_resolve_process_command([_apply_template(item, context) for item in spec.command]),
        env={key: _apply_template(value, context) for key, value in spec.env.items()},
        cwd=_apply_template(spec.cwd, context) if spec.cwd is not None else None,
        ready_pattern=_apply_template(spec.ready_pattern, context) if spec.ready_pattern is not None else None,
        ready_timeout=spec.ready_timeout,
        run_timeout=spec.run_timeout,
        version_command=_resolve_process_command([_apply_template(item, context) for item in spec.version_command]) if spec.version_command is not None else None,
        image=_apply_template(spec.image, context) if spec.image is not None else None,
        enabled=spec.enabled,
        metadata=dict(spec.metadata),
        provenance_kind=spec.provenance_kind,
        implementation_source=_apply_template(spec.implementation_source, context) if spec.implementation_source is not None else None,
        implementation_identity=_apply_template(spec.implementation_identity, context) if spec.implementation_identity is not None else None,
        implementation_version=_apply_template(spec.implementation_version, context) if spec.implementation_version is not None else None,
    )



def _build_process_env(source_root: Path, spec: InteropProcessSpec, transcript_path: Path, negotiation_path: Path, context: Mapping[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(spec.env)
    pythonpath_parts = [str(source_root / 'src'), str(source_root)]
    if env.get('PYTHONPATH'):
        pythonpath_parts.append(env['PYTHONPATH'])
    env['PYTHONPATH'] = os.pathsep.join(pythonpath_parts)
    env['PYTHONUNBUFFERED'] = '1'
    env['INTEROP_BIND_HOST'] = context['bind_host']
    env['INTEROP_BIND_PORT'] = context['bind_port']
    env['INTEROP_TARGET_HOST'] = context['target_host']
    env['INTEROP_TARGET_PORT'] = context['target_port']
    env['INTEROP_ARTIFACT_DIR'] = context['artifact_dir']
    env['INTEROP_PACKET_TRACE_PATH'] = context['packet_trace_path']
    env['INTEROP_QLOG_PATH'] = context['qlog_path']
    env['INTEROP_TRANSCRIPT_PATH'] = str(transcript_path)
    env['INTEROP_NEGOTIATION_PATH'] = str(negotiation_path)
    env['INTEROP_SCENARIO_ID'] = context['scenario_id']
    env['INTEROP_MATRIX_NAME'] = context['matrix_name']
    env['INTEROP_COMMIT_HASH'] = context['commit_hash']
    env['INTEROP_PROTOCOL'] = context['protocol']
    env['INTEROP_FEATURE'] = context['feature']
    env['INTEROP_ROLE'] = spec.role
    env['INTEROP_IP_FAMILY'] = context['ip_family']
    if context.get('retry'):
        env['INTEROP_ENABLE_RETRY'] = '1'
    if context.get('resumption'):
        env['INTEROP_ENABLE_RESUMPTION'] = '1'
    if context.get('zero_rtt'):
        env['INTEROP_ENABLE_ZERO_RTT'] = '1'
    if context.get('key_update'):
        env['INTEROP_ENABLE_KEY_UPDATE'] = '1'
    if context.get('migration'):
        env['INTEROP_ENABLE_MIGRATION'] = '1'
    if context.get('goaway'):
        env['INTEROP_ENABLE_GOAWAY'] = '1'
    if context.get('qpack_blocking'):
        env['INTEROP_ENABLE_QPACK_BLOCKING'] = '1'
    if context.get('cipher_group'):
        env['INTEROP_CIPHER_GROUP'] = context['cipher_group']
    return env



def _snapshot_interop_env(env: Mapping[str, str], spec: InteropProcessSpec) -> dict[str, str]:
    explicit_keys = set(spec.env)
    return {
        key: str(value)
        for key, value in sorted(env.items())
        if key.startswith('INTEROP_') or key in explicit_keys
    }

__all__ = [name for name in globals() if not name.startswith('__')]
