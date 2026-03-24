from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class InteropWrapper:
    wrapper_id: str
    family: str
    module: str
    implementation_source: str
    implementation_identity: str
    provenance_kind: str
    default_name: str
    supported_protocols: tuple[str, ...] = ()
    supported_features: tuple[str, ...] = ()
    runtime_dependencies: tuple[str, ...] = ()
    default_args: tuple[str, ...] = ()
    version_args: tuple[str, ...] = ('--version',)
    adapter: str = 'subprocess'
    role: str = 'client'
    notes: str = ''

    def build_process_spec(
        self,
        *,
        extra_args: Iterable[str] = (),
        env: Mapping[str, str] | None = None,
        name: str | None = None,
        python_bin: str | None = None,
        implementation_version: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        runner = python_bin or os.environ.get('TIGRCORN_INTEROP_PYTHON') or sys.executable
        payload: dict[str, Any] = {
            'name': name or self.default_name,
            'adapter': self.adapter,
            'role': self.role,
            'command': [runner, '-m', self.module, *self.default_args, *list(extra_args)],
            'version_command': [runner, '-m', self.module, *self.version_args],
            'provenance_kind': self.provenance_kind,
            'implementation_source': self.implementation_source,
            'implementation_identity': self.implementation_identity,
        }
        if env:
            payload['env'] = {str(key): str(value) for key, value in env.items()}
        if implementation_version is not None:
            payload['implementation_version'] = str(implementation_version)
        if metadata:
            payload['metadata'] = {str(key): value for key, value in metadata.items()}
        return payload

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['default_args'] = list(self.default_args)
        payload['runtime_dependencies'] = list(self.runtime_dependencies)
        payload['supported_features'] = list(self.supported_features)
        payload['supported_protocols'] = list(self.supported_protocols)
        payload['version_args'] = list(self.version_args)
        return payload


WRAPPER_REGISTRY: dict[str, InteropWrapper] = {
    'curl.http1_client': InteropWrapper(
        wrapper_id='curl.http1_client',
        family='curl',
        module='tests.fixtures_pkg.external_curl_client',
        implementation_source='curl project',
        implementation_identity='curl',
        provenance_kind='third_party_binary',
        default_name='curl-http1-client',
        default_args=('--http1',),
        supported_protocols=('http1',),
        supported_features=('post-echo', 'content-coding', 'trailers', 'connect-relay'),
        runtime_dependencies=('curl',),
        notes='Standard wrapper for HTTP/1.1 third-party curl interop scenarios.',
    ),
    'curl.http2_client': InteropWrapper(
        wrapper_id='curl.http2_client',
        family='curl',
        module='tests.fixtures_pkg.external_curl_client',
        implementation_source='curl project',
        implementation_identity='curl',
        provenance_kind='third_party_binary',
        default_name='curl-http2-client',
        default_args=('--http2',),
        supported_protocols=('http2',),
        supported_features=('post-echo', 'content-coding', 'trailers'),
        runtime_dependencies=('curl',),
        notes='Standard wrapper for HTTP/2 third-party curl interop scenarios.',
    ),
    'websockets.http11_client': InteropWrapper(
        wrapper_id='websockets.http11_client',
        family='websockets',
        module='tests.fixtures_pkg.external_websocket_client',
        implementation_source='websockets',
        implementation_identity='websockets-client',
        provenance_kind='third_party_library',
        default_name='websockets-client',
        supported_protocols=('websocket', 'http1'),
        supported_features=('text-echo', 'permessage-deflate'),
        runtime_dependencies=('websockets',),
        notes='Standard wrapper for HTTP/1.1 WebSocket scenarios using the third-party websockets client.',
    ),
    'h2.http2_client': InteropWrapper(
        wrapper_id='h2.http2_client',
        family='h2',
        module='tests.fixtures_pkg.external_h2_http_client',
        implementation_source='python-h2',
        implementation_identity='h2-http-client',
        provenance_kind='third_party_library',
        default_name='h2-http-client',
        supported_protocols=('http2',),
        supported_features=('post-echo', 'connect-relay', 'trailers'),
        runtime_dependencies=('h2',),
        notes='Standard wrapper for HTTP/2 request/response scenarios using python-h2.',
    ),
    'h2.http2_websocket_client': InteropWrapper(
        wrapper_id='h2.http2_websocket_client',
        family='h2',
        module='tests.fixtures_pkg.external_h2_websocket_client',
        implementation_source='python-h2/wsproto',
        implementation_identity='h2-websocket-client',
        provenance_kind='third_party_library',
        default_name='h2-websocket-client',
        supported_protocols=('http2', 'websocket'),
        supported_features=('websocket-extended-connect', 'permessage-deflate'),
        runtime_dependencies=('h2', 'wsproto'),
        notes='Standard wrapper for RFC 8441 and RFC 7692 WebSocket-over-HTTP/2 scenarios.',
    ),
    'aioquic.http3_client': InteropWrapper(
        wrapper_id='aioquic.http3_client',
        family='aioquic',
        module='tests.fixtures_third_party.aioquic_http3_client',
        implementation_source='aioquic',
        implementation_identity='aioquic-http3-client',
        provenance_kind='third_party_library',
        default_name='aioquic-http3-client',
        supported_protocols=('http3',),
        supported_features=('post-echo', 'content-coding', 'trailers', 'connect-relay'),
        runtime_dependencies=('aioquic',),
        notes='Standard wrapper for HTTP/3 request/response and semantic interop scenarios using aioquic.',
    ),
    'aioquic.http3_websocket_client': InteropWrapper(
        wrapper_id='aioquic.http3_websocket_client',
        family='aioquic',
        module='tests.fixtures_third_party.aioquic_http3_websocket_client',
        implementation_source='aioquic',
        implementation_identity='aioquic-http3-websocket-client',
        provenance_kind='third_party_library',
        default_name='aioquic-http3-websocket-client',
        supported_protocols=('http3', 'websocket'),
        supported_features=('websocket-rfc9220-echo', 'permessage-deflate'),
        runtime_dependencies=('aioquic', 'wsproto'),
        notes='Standard wrapper for RFC 9220 and RFC 7692 WebSocket-over-HTTP/3 scenarios using aioquic.',
    ),

    'openssl.tls_client': InteropWrapper(
        wrapper_id='openssl.tls_client',
        family='openssl',
        module='tests.fixtures_pkg.external_openssl_tls_client',
        implementation_source='openssl',
        implementation_identity='openssl-tls-client',
        provenance_kind='third_party_binary',
        default_name='openssl-tls-client',
        supported_protocols=('tls', 'http1'),
        supported_features=('ocsp-revocation', 'mtls-http1'),
        runtime_dependencies=('openssl',),
        notes='Standard wrapper for OpenSSL TLS/mTLS validation and OCSP-oriented scenarios.',
    ),
    'openssl.quic_client': InteropWrapper(
        wrapper_id='openssl.quic_client',
        family='openssl',
        module='tests.fixtures_pkg.external_openssl_quic_client',
        implementation_source='openssl',
        implementation_identity='openssl-quic-client',
        provenance_kind='third_party_binary',
        default_name='openssl-quic-client',
        supported_protocols=('quic', 'quic-tls', 'http3'),
        supported_features=('quic-tls-handshake', 'ocsp-revocation'),
        runtime_dependencies=('openssl',),
        notes='Standard wrapper for OpenSSL QUIC/TLS validation and OCSP-oriented scenarios.',
    ),
}


def get_wrapper(wrapper_id: str) -> InteropWrapper:
    try:
        return WRAPPER_REGISTRY[wrapper_id]
    except KeyError as exc:
        raise KeyError(f'unknown wrapper_id: {wrapper_id}') from exc


def describe_wrapper_registry() -> dict[str, Any]:
    families: dict[str, list[str]] = {}
    for wrapper in WRAPPER_REGISTRY.values():
        families.setdefault(wrapper.family, []).append(wrapper.wrapper_id)
    return {
        'schema_version': 1,
        'module': 'tools.interop_wrappers',
        'families': {family: sorted(ids) for family, ids in sorted(families.items())},
        'wrappers': {wrapper_id: wrapper.to_metadata() for wrapper_id, wrapper in sorted(WRAPPER_REGISTRY.items())},
    }


def write_wrapper_registry_json(path: str | Path) -> None:
    target = Path(path)
    target.write_text(json.dumps(describe_wrapper_registry(), indent=2, sort_keys=True) + '\n', encoding='utf-8')
