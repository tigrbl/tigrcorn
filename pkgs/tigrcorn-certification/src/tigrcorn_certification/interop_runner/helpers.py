from __future__ import annotations

from .imports import *

def _apply_template(value: str, context: Mapping[str, str]) -> str:
    try:
        return value.format_map(context)
    except KeyError:
        return value



def _artifact_metadata(path: Path) -> dict[str, Any]:
    return {
        'path': str(path),
        'exists': path.exists(),
        'size': path.stat().st_size if path.exists() else 0,
        'sha256': _sha256_path(path) if path.exists() else None,
    }



def _probe_command(command: list[str]) -> dict[str, Any]:
    executable = shutil.which(command[0])
    payload: dict[str, Any] = {'command': command, 'executable': executable, 'available': executable is not None}
    if executable is None:
        return payload
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5.0)
        payload['exit_code'] = completed.returncode
        payload['stdout'] = completed.stdout.strip()
        payload['stderr'] = completed.stderr.strip()
    except Exception as exc:
        payload['error'] = str(exc)
    return payload



def _load_json_if_present(path: Path) -> Any:
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return None
    return json.loads(text)



def _extract_cli_option(command: Sequence[str], flag: str) -> str | None:
    for index, item in enumerate(command):
        if item == flag and index + 1 < len(command):
            return command[index + 1]
    return None



def _resolve_cli_path(value: str | None, source_root: Path) -> str | None:
    if value in (None, ''):
        return None
    root = source_root.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    if path.exists() and (path == root or root in path.parents):
        return str(path.relative_to(root))
    return str(path)



def _synthesize_sut_transcript(
    *,
    scenario: InteropScenario,
    sut_spec: InteropProcessSpec,
    sut_result: InteropProcessResult,
    peer_transcript: Any,
) -> dict[str, Any]:
    peer_request = peer_transcript.get('request') if isinstance(peer_transcript, dict) else None
    peer_response = peer_transcript.get('response') if isinstance(peer_transcript, dict) else None
    return {
        'observation_model': 'interop_runner_synthesized_from_peer_observation',
        'scenario_id': scenario.id,
        'protocol': scenario.protocol,
        'feature': scenario.feature,
        'role': 'server',
        'request': peer_request,
        'response': peer_response,
        'server_process': {
            'name': sut_spec.name,
            'adapter': sut_spec.adapter,
            'role': sut_spec.role,
            'implementation_source': sut_result.provenance.get('implementation_source'),
            'implementation_identity': sut_result.provenance.get('implementation_identity'),
            'implementation_version': sut_result.provenance.get('implementation_version'),
            'exit_code': sut_result.exit_code,
            'stdout_path': sut_result.stdout_path,
            'stderr_path': sut_result.stderr_path,
        },
        'derived_from_peer_transcript': isinstance(peer_transcript, dict),
    }



def _synthesize_sut_negotiation(
    *,
    scenario: InteropScenario,
    sut_spec: InteropProcessSpec,
    sut_result: InteropProcessResult,
    peer_negotiation: Any,
    peer_transcript: Any,
    source_root: Path,
) -> dict[str, Any]:
    peer_map = peer_negotiation if isinstance(peer_negotiation, dict) else {}
    peer_response = peer_transcript.get('response') if isinstance(peer_transcript, dict) else {}
    response_extension_header = peer_map.get('response_extension_header')
    if response_extension_header in (None, '') and isinstance(peer_response, dict):
        response_extension_header = peer_response.get('extension_header')
    negotiated_extensions = list(peer_map.get('negotiated_extensions') or [])
    if not negotiated_extensions and isinstance(response_extension_header, str) and response_extension_header.lower().startswith('permessage-deflate'):
        negotiated_extensions = ['PerMessageDeflate']
    ssl_certfile = _resolve_cli_path(_extract_cli_option(sut_spec.command, '--ssl-certfile'), source_root)
    ssl_keyfile = _resolve_cli_path(_extract_cli_option(sut_spec.command, '--ssl-keyfile'), source_root)
    return {
        'observation_model': 'interop_runner_synthesized_from_peer_observation',
        'scenario_id': scenario.id,
        'protocol': peer_map.get('protocol') or scenario.protocol,
        'feature': scenario.feature,
        'role': 'server',
        'implementation': sut_result.provenance.get('implementation_source') or sut_spec.implementation_source or sut_spec.name,
        'implementation_source': sut_result.provenance.get('implementation_source'),
        'implementation_identity': sut_result.provenance.get('implementation_identity'),
        'implementation_version': sut_result.provenance.get('implementation_version'),
        'handshake_complete': peer_map.get('handshake_complete'),
        'compression_requested': peer_map.get('compression_requested'),
        'response_extension_header': response_extension_header,
        'negotiated_extensions': negotiated_extensions,
        'connect_protocol_enabled': peer_map.get('connect_protocol_enabled'),
        'settings_enable_connect_protocol': peer_map.get('settings_enable_connect_protocol'),
        'certificate_inputs': {
            'server_certfile': {
                'path': ssl_certfile,
                'exists': bool(ssl_certfile),
            },
            'server_keyfile': {
                'path': ssl_keyfile,
                'exists': bool(ssl_keyfile),
            },
        },
        'derived_from_peer_negotiation': isinstance(peer_negotiation, dict),
    }



def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')



def _safe_name(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', value).strip('-') or 'scenario'



def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()



def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

__all__ = [name for name in globals() if not name.startswith('__')]
