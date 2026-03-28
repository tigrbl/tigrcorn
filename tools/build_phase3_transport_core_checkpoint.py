from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.protocols.http1.parser import http11_request_head_error_matrix
from tigrcorn.protocols.http1.serializer import http11_response_metadata_rules
from tigrcorn.protocols.http2.state import h2_connection_rule_table, h2_stream_transition_table
from tigrcorn.protocols.http3.state import (
    http3_control_stream_rule_table,
    http3_qpack_accounting_rule_table,
    http3_request_transition_table,
)
from tigrcorn.security.tls13.handshake import tls13_handshake_state_table
from tigrcorn.transports.quic.connection import quic_connection_state_table, quic_transport_error_matrix
from tigrcorn.transports.quic.recovery import quic_recovery_rule_table
from tigrcorn.transports.quic.streams import quic_packet_space_legality_table, quic_packet_space_prohibitions


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'review' / 'conformance' / 'phase3_transport_core'


def _write_json(name: str, payload: object) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + '\n', encoding='utf-8')



def main() -> None:
    _write_json('http11_error_matrix.json', list(http11_request_head_error_matrix()))
    _write_json('http11_response_metadata_rules.json', list(http11_response_metadata_rules()))
    _write_json('http2_stream_transition_table.json', list(h2_stream_transition_table()))
    _write_json('http2_connection_rules.json', list(h2_connection_rule_table()))
    _write_json('http3_request_transition_table.json', list(http3_request_transition_table()))
    _write_json('http3_control_stream_rules.json', list(http3_control_stream_rule_table()))
    _write_json('http3_qpack_accounting_rules.json', list(http3_qpack_accounting_rule_table()))
    _write_json('quic_packet_space_legality.json', quic_packet_space_legality_table())
    _write_json('quic_packet_space_prohibitions.json', list(quic_packet_space_prohibitions()))
    _write_json('quic_recovery_rules.json', list(quic_recovery_rule_table()))
    _write_json('quic_connection_state_table.json', list(quic_connection_state_table()))
    _write_json('quic_transport_error_matrix.json', list(quic_transport_error_matrix()))
    _write_json('tls13_handshake_state_table.json', list(tls13_handshake_state_table()))

    evidence_manifest = {
        'release': '0.3.9',
        'bundle': 'phase3_transport_core_strictness_checkpoint',
        'scenario_classes': [
            {
                'class': 'http11_framing_and_origin_form_runtime',
                'artifact': 'docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-certification-release-matrix/http1-server-curl-client/result.json',
            },
            {
                'class': 'http2_frame_and_stream_state_runtime',
                'artifact': 'docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-certification-release-matrix/http2-server-h2-client/result.json',
            },
            {
                'class': 'http3_goaway_and_qpack_runtime',
                'artifact': 'docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-certification-release-matrix/http3-server-aioquic-client-post-goaway-qpack/result.json',
            },
            {
                'class': 'quic_retry_runtime',
                'artifact': 'docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-mixed-compatibility-release-matrix/http3-server-public-client-post-retry/result.json',
            },
            {
                'class': 'quic_resumption_runtime',
                'artifact': 'docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-mixed-compatibility-release-matrix/http3-server-public-client-post-resumption/result.json',
            },
            {
                'class': 'quic_path_migration_runtime',
                'artifact': 'docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-independent-certification-release-matrix/http3-server-aioquic-client-post-migration/result.json',
            },
        ],
    }
    _write_json('interop_evidence_manifest.json', evidence_manifest)

    (OUT / 'README.md').write_text(
        '# Phase 3 transport-core strictness snapshot\n\n'
        'This directory is machine-generated from runtime-exported strictness tables and preserved release artifacts.\n',
        encoding='utf-8',
    )


if __name__ == '__main__':
    main()
