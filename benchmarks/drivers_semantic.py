
from __future__ import annotations

from benchmarks.common import MemoryStreamReader, measure_async, measure_sync
from tigrcorn.protocols.connect import is_connect_allowed, parse_connect_authority
from tigrcorn.protocols.content_coding import apply_http_content_coding
from tigrcorn.protocols.http1.parser import _read_chunked_body

_CONNECT_ALLOW = ['127.0.0.1:443', '10.0.0.0/8']
_CHUNKED_WITH_TRAILERS = (
    b'3\r\nabc\r\n'
    b'3\r\ndef\r\n'
    b'0\r\nX-Trail: done\r\n\r\n'
)
_REQUEST_HEADERS = [(b'accept-encoding', b'gzip, deflate')]
_RESPONSE_HEADERS = [(b'content-type', b'text/plain')]
_PAYLOAD = b'tigrcorn semantic benchmark payload' * 4


def connect_relay_driver(profile, *, source_root):
    def operation():
        host, port = parse_connect_authority('127.0.0.1:443')
        allowed = is_connect_allowed(host, port, _CONNECT_ALLOW)
        return {
            'connections': 1,
            'correctness': {
                'authority_parse': host == '127.0.0.1' and port == 443,
                'allowlist_match': allowed,
            },
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def trailers_driver(profile, *, source_root):
    async def operation():
        body = await _read_chunked_body(MemoryStreamReader(_CHUNKED_WITH_TRAILERS), max_body_size=4096)
        return {
            'connections': 1,
            'correctness': {'trailers_tolerated': body == b'abcdef'},
            'metadata': {'body_size': len(body)},
        }
    return measure_async(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)


def content_coding_driver(profile, *, source_root):
    policy = str(profile.driver_config.get('policy', 'allowlist'))
    codings = tuple(profile.driver_config.get('codings', ['gzip', 'deflate']))
    def operation():
        status, headers, body, selection = apply_http_content_coding(
            request_headers=_REQUEST_HEADERS,
            response_headers=list(_RESPONSE_HEADERS),
            body=_PAYLOAD,
            status=200,
            policy=policy,
            supported=codings,
        )
        return {
            'connections': 1,
            'correctness': {
                'status_ok': status in {200, 406},
                'selection_valid': selection.coding in {None, 'gzip', 'deflate', 'br'},
                'body_nonempty': bool(body),
            },
            'metadata': {'response_headers': headers},
        }
    return measure_sync(operation, iterations=profile.iterations, warmups=profile.warmups, units_per_iteration=profile.units_per_iteration)
