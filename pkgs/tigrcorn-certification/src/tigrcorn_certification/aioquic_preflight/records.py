from __future__ import annotations

from .imports import *
from .helpers import *
from .helpers import _default_certificate_inputs, _load_json, _module_name, _path_ready, _scenario_kind

def _extract_scenario_record(repo_root: Path, bundle_root: Path, scenario_id: str) -> dict[str, Any]:
    scenario_root = bundle_root / scenario_id
    result = _load_json(scenario_root / 'result.json')
    commands = _load_json(scenario_root / 'command.json')
    versions = _load_json(scenario_root / 'versions.json')
    peer_command = [str(item) for item in commands['peer']['command']]
    negotiation = dict((result.get('negotiation') or {}).get('peer') or {})
    transcript = dict((result.get('transcript') or {}).get('peer') or {})
    transcript_quic = dict(transcript.get('quic') or {})
    certificate_inputs = dict(negotiation.get('certificate_inputs') or _default_certificate_inputs(repo_root, peer_command))
    handshake_complete = bool(
        negotiation.get('handshake_complete')
        or transcript_quic.get('handshake_complete')
        or (result.get('passed') and (result.get('peer') or {}).get('exit_code') == 0 and negotiation.get('protocol') == 'h3')
    )
    artifacts = result.get('artifacts') or {}
    response = dict(transcript.get('response') or {})

    return {
        'scenario_id': scenario_id,
        'kind': _scenario_kind(scenario_id),
        'passed': bool(result.get('passed')),
        'peer_exit_code': int((result.get('peer') or {}).get('exit_code') or 0),
        'peer_module': _module_name(peer_command),
        'peer_command': peer_command,
        'peer_version': (versions.get('peer') or {}).get('implementation_version'),
        'protocol': negotiation.get('protocol'),
        'tls_version': negotiation.get('tls_version'),
        'server_name': negotiation.get('server_name'),
        'handshake_complete': handshake_complete,
        'retry_observed': bool(negotiation.get('retry_observed')),
        'negotiation_metadata_emitted': bool((artifacts.get('peer_negotiation') or {}).get('exists')),
        'transcript_emitted': bool((artifacts.get('peer_transcript') or {}).get('exists')),
        'packet_trace_exists': bool((artifacts.get('packet_trace') or {}).get('exists')),
        'qlog_exists': bool((artifacts.get('qlog') or {}).get('exists')),
        'certificate_inputs': certificate_inputs,
        'certificate_inputs_ready': bool(negotiation.get('certificate_inputs_ready', certificate_inputs.get('ready'))),
        'ca_cert_path': (certificate_inputs.get('ca_cert') or {}).get('path'),
        'ca_cert_exists': _path_ready(certificate_inputs.get('ca_cert') or {}),
        'client_material_requested': bool(certificate_inputs.get('client_material_requested')),
        'response_status': response.get('status'),
        'websocket_connect_protocol_enabled': negotiation.get('connect_protocol_enabled'),
        'websocket_negotiated_extensions': list(negotiation.get('negotiated_extensions') or []),
        'artifact_dir': str(scenario_root.relative_to(bundle_root)),
        'result_path': str((scenario_root / 'result.json').relative_to(bundle_root)),
        'peer_negotiation_path': str((scenario_root / 'peer_negotiation.json').relative_to(bundle_root)),
        'peer_transcript_path': str((scenario_root / 'peer_transcript.json').relative_to(bundle_root)),
    }
