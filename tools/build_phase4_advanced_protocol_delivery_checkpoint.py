from __future__ import annotations

import json
from pathlib import Path

from tigrcorn.server.bootstrap import runtime_compatibility_matrix


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'review' / 'conformance' / 'phase4_advanced_protocol_delivery'


def _write_json(name: str, payload: object) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def main() -> None:
    _write_json('runtime_compatibility_matrix.json', runtime_compatibility_matrix())
    _write_json(
        'early_hints_support.json',
        {
            'feature': 'early_hints',
            'status': 'certified_authoritative_and_strict_local_conformance_target',
            'http_versions': ['1.1', '2', '3'],
            'interim_status_codes': [103],
            'safe_headers': ['link'],
            'certification_boundary': {
                'target_rfc': 'RFC 8297',
                'highest_required_evidence_tier': 'local_conformance',
                'corpus_vector': 'http-early-hints',
                'support_envelope': 'direct_server_103_early_hints',
            },
            'notes': [
                'unsafe headers are stripped from 103 responses',
                'Early Hints are emitted before the final response head/block',
                'public support envelope is limited to direct server delivery behavior',
            ],
        },
    )
    _write_json(
        'alt_svc_surface.json',
        {
            'feature': 'alt_svc',
            'status': 'certified_authoritative_and_strict_local_conformance_target',
            'config_surface': {
                'cli_flags': ['--alt-svc', '--alt-svc-auto', '--no-alt-svc-auto', '--alt-svc-ma', '--alt-svc-persist'],
                'config_fields': ['http.alt_svc_headers', 'http.alt_svc_auto', 'http.alt_svc_max_age', 'http.alt_svc_persist'],
                'env_fields': ['TIGRCORN_ALT_SVC', 'TIGRCORN_ALT_SVC_AUTO', 'TIGRCORN_ALT_SVC_MAX_AGE', 'TIGRCORN_ALT_SVC_PERSIST'],
            },
            'certification_boundary': {
                'target_rfc': 'RFC 7838 §3',
                'highest_required_evidence_tier': 'local_conformance',
                'corpus_vector': 'http-alt-svc-header-advertisement',
                'support_envelope': 'header_field_advertisement_only',
            },
            'notes': [
                'explicit Alt-Svc headers override automatic advertisement',
                'automatic advertisement derives h3 endpoints from UDP HTTP/3 listeners',
                'automatic Alt-Svc is suppressed on HTTP/3 responses',
                'the current certification boundary does not claim broader protocol-level Alt-Svc framing surfaces',
            ],
            'non_targeted_surfaces': ['RFC 9218 prioritization'],
        },
    )
    _write_json(
        'static_delivery_status.json',
        {
            'feature': 'static_files',
            'status': 'checkpoint_hardened',
            'supports': ['etag', 'last-modified', 'conditional requests', 'byte ranges', 'HEAD', 'gzip', 'brotli', 'safe path normalization'],
            'known_partials': [
                'whole-file reads are still buffered in memory in this checkpoint',
                'this is not yet a zero-copy or sendfile-oriented implementation',
            ],
        },
    )
    _write_json(
        'example_matrix.json',
        {
            'bundle': 'phase4_advanced_protocol_delivery_checkpoint',
            'lanes': [
                {'lane': 'http1_basic', 'server': 'examples/echo_http/app.py', 'client': 'curl or raw socket'},
                {'lane': 'http2_basic', 'server': 'examples/echo_http/app.py', 'client': 'tests/fixtures_pkg/external_h2_http_client.py'},
                {'lane': 'http3_basic', 'server': 'examples/echo_http/app.py', 'client': 'tests/fixtures_pkg/external_http3_client.py'},
                {'lane': 'websocket', 'server': 'examples/websocket_echo/app.py', 'client': 'tests/fixtures_pkg/external_websocket_client.py'},
                {'lane': 'permessage_deflate', 'server': 'examples/websocket_echo/app.py', 'client': 'tests/fixtures_pkg/external_websocket_client.py'},
                {'lane': 'connect', 'server': 'tests/fixtures_pkg/_connect_relay_fixture.py', 'client': 'tests/fixtures_pkg/interop_http_client.py'},
                {'lane': 'trailers', 'server': 'tests/fixtures_pkg/interop_trailer_app.py', 'client': 'repository trailer tests and external HTTP clients'},
                {'lane': 'content_coding', 'server': 'tests/fixtures_pkg/interop_content_coding_app.py', 'client': 'tests/fixtures_pkg/external_curl_client.py'},
                {'lane': 'static_range_etag', 'server': 'examples/http_entity_static/app.py', 'client': 'examples/http_entity_static/client_http1.py'},
                {'lane': 'early_hints', 'server': 'examples/advanced_protocol_delivery/early_hints_app.py', 'client': 'examples/advanced_protocol_delivery/early_hints_client_http1.py'},
                {'lane': 'alt_svc', 'server': 'examples/advanced_protocol_delivery/alt_svc_app.py', 'client': 'examples/advanced_protocol_delivery/alt_svc_client_http1.py'},
                {'lane': 'runtime_embedding', 'server': 'examples/advanced_protocol_delivery/runtime_embedding.py', 'client': 'embedded python host process'},
            ],
        },
    )
    (OUT / 'README.md').write_text(
        '# Phase 4 advanced protocol and delivery checkpoint snapshot\n\n'
        'This directory is machine-generated for the Phase 4 checkpoint and records the public support surface added in this delivery.\n',
        encoding='utf-8',
    )


if __name__ == '__main__':
    main()
