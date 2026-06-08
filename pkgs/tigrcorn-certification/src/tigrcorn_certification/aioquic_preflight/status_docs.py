from __future__ import annotations

from .imports import *

def _status_markdown(snapshot: Mapping[str, Any], *, release_root: str, bundle_root: str) -> str:
    current = snapshot['current_state']
    scenario_records = current['scenario_records']
    lines = [
        '# aioquic adapter preflight',
        '',
        'This checkpoint executes the third-party aioquic HTTP/3 adapters directly before any strict-target artifact-promotion work proceeds.',
        '',
        '## Exit criteria',
        '',
        f"- both adapters passed: `{current['all_adapters_passed']}`",
        f"- no peer exit code 2: `{current['no_peer_exit_code_2']}`",
        f"- negotiation metadata emitted: `{current['negotiation_metadata_emitted']}`",
        f"- transcript metadata emitted: `{current['transcript_metadata_emitted']}`",
        f"- ALPN h3 observed: `{current['all_protocols_h3']}`",
        f"- QUIC handshakes complete: `{current['all_handshakes_complete']}`",
        f"- certificate inputs ready: `{current['certificate_inputs_ready']}`",
        '',
        '## Environment snapshot',
        '',
        f"- python version: `{current['environment']['python_version']}`",
        f"- python minor version: `{current['environment']['python_minor_version']}`",
        f"- aioquic version: `{current['environment']['aioquic_version']}`",
        f"- wsproto version: `{current['environment']['wsproto_version']}`",
        f"- h2 version: `{current['environment']['h2_version']}`",
        f"- websockets version: `{current['environment']['websockets_version']}`",
        f"- release root: `{release_root}`",
        f"- preflight bundle root: `{bundle_root}`",
        '',
        '## Scenario results',
        '',
    ]
    for item in scenario_records:
        lines.extend([
            f"### `{item['scenario_id']}`",
            '',
            f"- kind: `{item['kind']}`",
            f"- adapter module: `{item['peer_module']}`",
            f"- peer exit code: `{item['peer_exit_code']}`",
            f"- protocol: `{item['protocol']}`",
            f"- tls version: `{item['tls_version']}`",
            f"- server name: `{item['server_name']}`",
            f"- handshake complete: `{item['handshake_complete']}`",
            f"- ca cert path: `{item['ca_cert_path']}`",
            f"- ca cert exists: `{item['ca_cert_exists']}`",
            f"- certificate inputs ready: `{item['certificate_inputs_ready']}`",
            f"- packet trace emitted: `{item['packet_trace_exists']}`",
            f"- qlog emitted: `{item['qlog_exists']}`",
            f"- peer negotiation metadata: `{item['peer_negotiation_path']}`",
            f"- peer transcript metadata: `{item['peer_transcript_path']}`",
            '',
        ])
    lines.extend([
        '## Honest current repository state',
        '',
        f"- authoritative boundary after preflight: `{current['gate_status_after_preflight']['authoritative_boundary_passed']}`",
        f"- strict target after preflight: `{current['gate_status_after_preflight']['strict_target_boundary_passed']}`",
        f"- promotion target after preflight: `{current['gate_status_after_preflight']['promotion_target_passed']}`",
        '',
        'This preflight closes the adapter-execution ambiguity: the aioquic HTTP/3 client and aioquic RFC 9220 WebSocket client both ran successfully and emitted negotiation metadata. It does **not** by itself promote the remaining strict-target HTTP/3 scenario artifacts into the 0.3.9 release root, so the package may still remain non-green under the stricter target until those artifacts are regenerated and assembled.',
        '',
    ])
    return '\n'.join(lines)


def _delivery_notes(snapshot: Mapping[str, Any], *, release_root: str, bundle_root: str) -> str:
    current = snapshot['current_state']
    return (
        '# Delivery notes — aioquic adapter preflight\n\n'
        'This checkpoint adds a direct aioquic adapter preflight on top of the existing release-assembly repository.\n\n'
        'What changed:\n\n'
        '- added a reusable aioquic preflight module at `src/tigrcorn/compat/aioquic_preflight.py`\n'
        '- added a runnable checkpoint tool at `tools/preflight_aioquic_adapters.py`\n'
        '- added a preserved preflight bundle under the 0.3.9 working release root\n'
        '- updated the release workflow and local wrapper so aioquic adapter preflight is now mandatory before release checkpoint scripts run\n'
        '- updated current-state documentation\n\n'
        'Current result:\n\n'
        f"- preflight bundle root: `{bundle_root}`\n"
        f"- all adapters passed: `{current['all_adapters_passed']}`\n"
        f"- no peer exit code 2: `{current['no_peer_exit_code_2']}`\n"
        f"- strict target after preflight: `{current['gate_status_after_preflight']['strict_target_boundary_passed']}`\n"
        f"- promotion target after preflight: `{current['gate_status_after_preflight']['promotion_target_passed']}`\n\n"
        'This checkpoint proves the third-party aioquic adapter execution path is healthy in the observed environment. It does not by itself claim that the package is already strict-target green or promotable.\n'
    )
def write_status_documents(
    root: str | Path,
    snapshot: Mapping[str, Any],
    *,
    release_root: str = DEFAULT_RELEASE_ROOT,
    bundle_root: str = DEFAULT_BUNDLE_NAME,
    status_doc: str = DEFAULT_STATUS_DOC,
    status_json: str = DEFAULT_STATUS_JSON,
    delivery_notes: str = DEFAULT_DELIVERY_NOTES,
) -> None:
    repo_root = Path(root)
    _dump_json(repo_root / status_json, snapshot)
    (repo_root / status_doc).write_text(
        _status_markdown(snapshot, release_root=release_root, bundle_root=bundle_root),
        encoding='utf-8',
    )
    (repo_root / delivery_notes).write_text(
        _delivery_notes(snapshot, release_root=release_root, bundle_root=bundle_root),
        encoding='utf-8',
    )
