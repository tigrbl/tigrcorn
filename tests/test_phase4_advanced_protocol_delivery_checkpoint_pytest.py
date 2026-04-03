from __future__ import annotations

import asyncio
import gzip
import json
import socket
import tempfile
from pathlib import Path

import pytest
from tigrcorn import EmbeddedServer, StaticFilesApp
from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.constants import H2_PREFACE
from tigrcorn.http.alt_svc import configured_alt_svc_values
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import HPACKDecoder, decode_header_block, encode_header_block
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.server.bootstrap import runtime_compatibility_matrix
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection


async def _start_server(
    app,
    *,
    tcp_versions: list[str] | None = None,
    include_udp_http3: bool = False,
    alt_svc_auto: bool = False,
    alt_svc: list[str] | None = None,
):
    config = build_config(
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=tcp_versions or ['1.1'],
        quic_secret=b'shared',
        alt_svc_auto=alt_svc_auto,
        alt_svc=alt_svc,
    )
    if include_udp_http3:
        config.listeners.append(
            ListenerConfig(
                kind='udp',
                host='127.0.0.1',
                port=0,
                http_versions=['3'],
                protocols=['http3'],
                quic_secret=b'shared',
            )
        )
    server = TigrCornServer(app, config)
    await server.start()
    tcp_port = None
    udp_port = None
    for listener in server._listeners:
        if hasattr(listener, 'server') and getattr(listener, 'server', None) is not None:
            sockets = listener.server.sockets or []
            if sockets:
                tcp_port = sockets[0].getsockname()[1]
        if hasattr(listener, 'transport') and getattr(listener, 'transport', None) is not None:
            udp_port = listener.transport.get_extra_info('sockname')[1]
    return server, tcp_port, udp_port


async def _read_http1_response(reader: asyncio.StreamReader) -> tuple[bytes, dict[bytes, bytes], bytes]:
    head = await reader.readuntil(b'\r\n\r\n')
    headers: dict[bytes, bytes] = {}
    for line in head.split(b'\r\n')[1:]:
        if not line:
            continue
        name, value = line.split(b':', 1)
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get(b'content-length', b'0'))
    body = await reader.readexactly(length) if length else b''
    return head, headers, body


async def _read_h2_response_sequence(reader: asyncio.StreamReader) -> tuple[list[list[tuple[bytes, bytes]]], bytes]:
    buf = FrameBuffer()
    decoder = HPACKDecoder()
    header_blocks: list[list[tuple[bytes, bytes]]] = []
    body = bytearray()
    ended = False
    while not ended:
        data = await asyncio.wait_for(reader.read(65535), 2.0)
        assert data
        buf.feed(data)
        for frame in buf.pop_all():
            if frame.frame_type == FRAME_SETTINGS and frame.payload:
                decode_settings(frame.payload)
            elif frame.frame_type == FRAME_HEADERS:
                header_blocks.append(decoder.decode_header_block(frame.payload))
                if frame.flags & 0x1:
                    ended = True
            elif frame.frame_type == FRAME_DATA:
                body.extend(frame.payload)
                if frame.flags & 0x1:
                    ended = True
        if header_blocks and ended:
            break
    return header_blocks, bytes(body)


async def _prime_http3(sock: socket.socket, client: QuicConnection, core: HTTP3ConnectionCore, *, port: int) -> None:
    loop = asyncio.get_running_loop()
    sock.sendto(client.build_initial(), ('127.0.0.1', port))
    received = 0
    for _ in range(4):
        try:
            data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
        except TimeoutError:
            if received:
                break
            raise
        received += 1
        for event in client.receive_datagram(data):
            if event.kind == 'stream':
                core.receive_stream_data(event.stream_id, event.data, fin=event.fin)


async def _read_h3_response_state(sock: socket.socket, client: QuicConnection, core: HTTP3ConnectionCore, *, stream_id: int):
    loop = asyncio.get_running_loop()
    response_state = None
    while response_state is None or not response_state.ended:
        data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
        for event in client.receive_datagram(data):
            if event.kind == 'stream':
                state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
                if event.stream_id == stream_id:
                    response_state = state
    assert response_state is not None
    return response_state


def test_runtime_compatibility_matrix_is_honest():
    matrix = runtime_compatibility_matrix()
    assert set(matrix) == {'auto', 'asyncio', 'uvloop'}
    assert matrix['auto']['implemented']
    assert 'trio' not in matrix

def test_public_runtime_surface_descopes_trio():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['tests.fixtures_pkg.appmod:app', '--runtime', 'trio'])
    matrix_path = Path('docs/review/conformance/phase4_advanced_delivery/runtime_compatibility_matrix.json')
    assert json.loads(matrix_path.read_text()) == runtime_compatibility_matrix()

def test_alt_svc_auto_values_resolve_and_suppress_on_http3():
    config = build_config(host='127.0.0.1', port=8080, lifespan='off', alt_svc_auto=True)
    config.listeners.append(
        ListenerConfig(
            kind='udp',
            host='127.0.0.1',
            port=8443,
            http_versions=['3'],
            protocols=['http3'],
            quic_secret=b'shared',
        )
    )
    assert configured_alt_svc_values(config, request_http_version='3') == []
    assert b'h3=":8443"; ma=86400' in configured_alt_svc_values(config, request_http_version='2')

def test_phase4_artifacts_and_examples_exist():
    expected = [
        Path('docs/review/conformance/phase4_advanced_delivery/early_hints_support_statement.json'),
        Path('docs/review/conformance/phase4_advanced_delivery/alt_svc_support_statement.json'),
        Path('docs/review/conformance/phase4_advanced_delivery/runtime_compatibility_matrix.json'),
        Path('docs/review/conformance/phase4_advanced_delivery/examples_matrix.json'),
        Path('docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json'),
        Path('docs/review/conformance/state/checkpoints/CURRENT_REPOSITORY_STATE_PHASE4_ADVANCED_PROTOCOL_DELIVERY_CHECKPOINT.md'),
        Path('examples/advanced_delivery/app.py'),
        Path('examples/advanced_delivery/client_http1.py'),
        Path('examples/advanced_delivery/client_http2.py'),
        Path('examples/advanced_delivery/client_http3.py'),
        Path('examples/PHASE4_PROTOCOL_PAIRING.md'),
    ]
    for path in expected:
        assert path.exists(), path

def test_phase4_status_json_is_honest():
    payload = json.loads(Path('docs/review/conformance/phase4_advanced_protocol_delivery_checkpoint.current.json').read_text())
    assert payload['phase'] == 4
    assert not (payload['boundary']['expanded_program_fully_featured'])
    assert not (payload['boundary']['expanded_program_fully_rfc_compliant'])
    assert payload['implemented']['runtime_embedding']['trio_surface'] == 'descoped_not_supported'
    assert payload['implemented']['runtime_embedding']['supported_runtimes'] == ['auto', 'asyncio', 'uvloop']


@pytest.mark.asyncio
async def test_static_files_precompressed_sidecars_and_range_identity_coexist():
    async def receive() -> dict:
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        payload = b'hello world from static sidecar'
        (root / 'hello.txt').write_bytes(payload)
        encoded = gzip.compress(payload)
        (root / 'hello.txt.gz').write_bytes(encoded)
        app = StaticFilesApp(root)

        await app({'type': 'http', 'method': 'GET', 'path': '/hello.txt', 'headers': [(b'accept-encoding', b'gzip')]}, receive, send)
        assert sent[0]['status'] == 200
        headers = dict(sent[0]['headers'])
        assert headers[b'content-encoding'] == b'gzip'
        assert headers[b'vary'] == b'accept-encoding'
        assert sent[1]['body'] == encoded

        sent.clear()
        await app({'type': 'http', 'method': 'HEAD', 'path': '/hello.txt', 'headers': [(b'accept-encoding', b'gzip')]}, receive, send)
        assert sent[0]['status'] == 200
        headers = dict(sent[0]['headers'])
        assert headers[b'content-length'] == str(len(encoded)).encode('ascii')
        assert sent[1]['body'] == b''

        sent.clear()
        await app(
            {
                'type': 'http',
                'method': 'GET',
                'path': '/hello.txt',
                'headers': [(b'accept-encoding', b'gzip'), (b'range', b'bytes=6-10')],
            },
            receive,
            send,
        )
        assert sent[0]['status'] == 206
        headers = dict(sent[0]['headers'])
        assert b'content-encoding' not in headers
        assert headers[b'content-range'] == b'bytes 6-10/31'
        assert sent[1]['body'] == b'world'


@pytest.mark.asyncio
async def test_embedded_server_context_manager_runs_hooks():
    events: list[str] = []

    async def app(scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'embedded', 'more_body': False})

    async def on_start(server) -> None:
        events.append('startup')

    async def on_stop(server) -> None:
        events.append('shutdown')

    config = build_config(host='127.0.0.1', port=0, lifespan='off')
    config.hooks.on_startup = [on_start]
    config.hooks.on_shutdown = [on_stop]

    async with EmbeddedServer(app, config) as embedded:
        endpoints = embedded.bound_endpoints()
        assert endpoints
        port = endpoints[0][1]
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        await writer.drain()
        _head, _headers, body = await _read_http1_response(reader)
        assert body == b'embedded'
        writer.close()
        await writer.wait_closed()
    assert events == ['startup', 'shutdown']

@pytest.mark.asyncio
async def test_http11_early_hints_and_alt_svc_auto():
    async def app(scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 103, 'headers': [(b'link', b'</app.js>; rel=preload; as=script'), (b'x-unsafe', b'no')]})
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

    server, port, udp_port = await _start_server(app, tcp_versions=['1.1'], include_udp_http3=True, alt_svc_auto=True)
    assert port is not None and udp_port is not None
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        await writer.drain()
        interim_head, interim_headers, interim_body = await _read_http1_response(reader)
        assert b'103 Early Hints' in interim_head
        assert interim_body == b''
        assert b'link' in interim_headers
        assert b'x-unsafe' not in interim_headers
        final_head, final_headers, final_body = await _read_http1_response(reader)
        assert b'200 OK' in final_head
        assert final_body == b'ok'
        assert final_headers[b'alt-svc'] == f'h3=":{udp_port}"; ma=86400'.encode('ascii')
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_http2_early_hints_and_alt_svc_auto():
    async def app(scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 103, 'headers': [(b'link', b'</app.css>; rel=preload; as=style'), (b'x-unsafe', b'no')]})
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

    server, port, udp_port = await _start_server(app, tcp_versions=['2'], include_udp_http3=True, alt_svc_auto=True)
    assert port is not None and udp_port is not None
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        frame_writer = FrameWriter()
        writer.write(H2_PREFACE)
        writer.write(serialize_settings({}))
        request_headers = encode_header_block([
            (b':method', b'GET'),
            (b':scheme', b'http'),
            (b':path', b'/'),
            (b':authority', b'localhost'),
        ])
        writer.write(frame_writer.headers(1, request_headers, end_stream=True))
        await writer.drain()
        header_blocks, body = await _read_h2_response_sequence(reader)
        assert len(header_blocks) >= 2
        interim = header_blocks[0]
        final = header_blocks[-1]
        assert (b':status', b'103') in interim
        assert (b'link', b'</app.css>; rel=preload; as=style') in interim
        assert (b'x-unsafe', b'no') not in interim
        assert (b':status', b'200') in final
        assert (b'alt-svc', f'h3=":{udp_port}"; ma=86400'.encode('ascii')) in final
        assert body == b'ok'
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_http3_early_hints_are_preserved_before_final_headers():
    async def app(scope, receive, send):
        await receive()
        await send({'type': 'http.response.start', 'status': 103, 'headers': [(b'link', b'</app.js>; rel=preload; as=script'), (b'x-unsafe', b'no')]})
        await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})

    server, _port, udp_port = await _start_server(app, tcp_versions=['1.1'], include_udp_http3=True, alt_svc_auto=True)
    assert udp_port is not None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'phase4-http3')
    core = HTTP3ConnectionCore(role='client')
    try:
        await _prime_http3(sock, client, core, port=udp_port)
        request_stream_id = 0
        payload = core.get_request(request_stream_id).encode_request([
            (b':method', b'GET'),
            (b':scheme', b'https'),
            (b':path', b'/'),
            (b':authority', b'localhost'),
        ])
        sock.sendto(client.send_stream_data(request_stream_id, payload, fin=True), ('127.0.0.1', udp_port))
        response_state = await _read_h3_response_state(sock, client, core, stream_id=request_stream_id)
        assert len(response_state.informational_headers) == 1
        assert (b':status', b'103') in response_state.informational_headers[0]
        assert (b'link', b'</app.js>; rel=preload; as=script') in response_state.informational_headers[0]
        assert (b'x-unsafe', b'no') not in response_state.informational_headers[0]
        assert (b':status', b'200') in response_state.headers
        assert response_state.body == b'ok'
    finally:
        sock.close()
        await server.close()

