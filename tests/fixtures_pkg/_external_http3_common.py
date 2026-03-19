from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from tigrcorn.constants import DEFAULT_QUIC_SECRET
from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.protocols.http3.codec import SETTING_ENABLE_CONNECT_PROTOCOL
from tigrcorn.protocols.http3.streams import SETTING_QPACK_BLOCKED_STREAMS, SETTING_QPACK_MAX_TABLE_CAPACITY
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver


def write_json(path_env: str, payload: dict[str, Any]) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def load_pem(path: str | None) -> bytes | None:
    if not path:
        return None
    return Path(path).read_bytes()


def env_flag(name: str) -> bool:
    value = os.environ.get(name, '')
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def make_client(
    *,
    server_name: str,
    trusted_certificates: list[bytes],
    client_cert: bytes | None = None,
    client_key: bytes | None = None,
    session_ticket: object | None = None,
    enable_early_data: bool = False,
) -> tuple[QuicConnection, HTTP3ConnectionCore]:
    client = QuicConnection(is_client=True, secret=DEFAULT_QUIC_SECRET, local_cid=os.urandom(8))
    driver = QuicTlsHandshakeDriver(
        is_client=True,
        server_name=server_name,
        trusted_certificates=trusted_certificates,
        certificate_pem=client_cert,
        private_key_pem=client_key,
        session_ticket=session_ticket,
        enable_early_data=enable_early_data,
    )
    client.configure_handshake(driver)
    return client, HTTP3ConnectionCore(role='client')


def send_pending(sock: socket.socket, client: QuicConnection, target: tuple[str, int]) -> None:
    for datagram in client.take_pending_datagrams():
        sock.sendto(datagram, target)


def recv_step(
    sock: socket.socket,
    client: QuicConnection,
    core: HTTP3ConnectionCore,
    *,
    timeout: float,
) -> tuple[list[Any], list[Any]]:
    sock.settimeout(timeout)
    data, addr = sock.recvfrom(65535)
    events = client.receive_datagram(data, addr=addr)
    stream_states: list[Any] = []
    for event in events:
        if getattr(event, 'kind', None) == 'stream':
            state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
            if state is not None:
                stream_states.append(state)
    return events, stream_states


def perform_handshake(
    sock: socket.socket,
    client: QuicConnection,
    core: HTTP3ConnectionCore,
    *,
    target: tuple[str, int],
    deadline: float,
    expect_connect_protocol: bool = False,
    start: bool = True,
) -> dict[str, Any]:
    observed: dict[str, Any] = {
        'retry_observed': False,
        'handshake_complete': False,
        'settings_seen': False,
    }
    if start:
        sock.sendto(client.start_handshake(), target)
    while time.monotonic() < deadline:
        send_pending(sock, client, target)
        try:
            events, _states = recv_step(sock, client, core, timeout=min(1.0, max(deadline - time.monotonic(), 0.05)))
        except socket.timeout:
            continue
        for event in events:
            if getattr(event, 'kind', None) == 'retry':
                observed['retry_observed'] = True
        send_pending(sock, client, target)
        if client.handshake_driver is not None and client.handshake_driver.complete:
            observed['handshake_complete'] = True
            if not expect_connect_protocol:
                return observed
            if core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
                observed['settings_seen'] = True
                return observed
        if expect_connect_protocol and core.state.remote_settings.get(SETTING_ENABLE_CONNECT_PROTOCOL) == 1:
            observed['settings_seen'] = True
            if client.handshake_driver is not None and client.handshake_driver.complete:
                observed['handshake_complete'] = True
                return observed
    raise RuntimeError('QUIC handshake did not complete before deadline')


def wait_for_session_ticket(
    sock: socket.socket,
    client: QuicConnection,
    core: HTTP3ConnectionCore,
    *,
    target: tuple[str, int],
    deadline: float,
) -> object | None:
    while time.monotonic() < deadline:
        driver = client.handshake_driver
        if driver is not None and getattr(driver, 'received_session_ticket', None) is not None:
            return driver.received_session_ticket
        send_pending(sock, client, target)
        try:
            recv_step(sock, client, core, timeout=min(0.5, max(deadline - time.monotonic(), 0.05)))
        except socket.timeout:
            continue
        send_pending(sock, client, target)
    driver = client.handshake_driver
    if driver is not None:
        return getattr(driver, 'received_session_ticket', None)
    return None


def open_client_control_stream(client: QuicConnection) -> int:
    return client.streams.next_stream_id(client=True, unidirectional=True)


def send_client_settings(
    sock: socket.socket,
    client: QuicConnection,
    core: HTTP3ConnectionCore,
    *,
    target: tuple[str, int],
    qpack_blocking: bool = False,
) -> int:
    settings = {1: 0, 6: 1200}
    if qpack_blocking:
        settings[SETTING_QPACK_MAX_TABLE_CAPACITY] = 256
        settings[SETTING_QPACK_BLOCKED_STREAMS] = 1
    control_stream_id = open_client_control_stream(client)
    payload = core.encode_control_stream(settings)
    sock.sendto(client.send_stream_data(control_stream_id, payload, fin=False), target)
    send_pending(sock, client, target)
    return control_stream_id


def exchange_request(
    sock: socket.socket,
    client: QuicConnection,
    core: HTTP3ConnectionCore,
    *,
    target: tuple[str, int],
    path: str,
    body: bytes,
    authority: bytes,
    deadline: float,
    migrate_after_send: bool = False,
    early_data: bool = False,
) -> tuple[Any, socket.socket, dict[str, Any]]:
    stream_id = 0
    request = core.get_request(stream_id)
    payload = request.encode_request(
        [
            (b':method', b'POST'),
            (b':path', path.encode('utf-8')),
            (b':scheme', b'https'),
            (b':authority', authority),
        ],
        body,
    )
    original_local = sock.getsockname()
    if early_data:
        sock.sendto(client.send_early_stream_data(stream_id, payload, fin=True), target)
    else:
        sock.sendto(client.send_stream_data(stream_id, payload, fin=True), target)
    send_pending(sock, client, target)
    migration: dict[str, Any] = {'used': False, 'from': list(original_local[:2])}
    if migrate_after_send:
        migrated = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        migrated.bind(('127.0.0.1', 0))
        migrated.settimeout(1.0)
        migration['used'] = True
        migration['to'] = list(migrated.getsockname()[:2])
        sock.close()
        sock = migrated
    response_state = None
    while time.monotonic() < deadline:
        send_pending(sock, client, target)
        try:
            _events, states = recv_step(sock, client, core, timeout=min(1.0, max(deadline - time.monotonic(), 0.05)))
        except socket.timeout:
            continue
        send_pending(sock, client, target)
        for state in states:
            if getattr(state, 'stream_id', None) == stream_id:
                response_state = state
        if response_state is not None and getattr(response_state, 'ended', False):
            return response_state, sock, migration
    raise RuntimeError('HTTP/3 response was not received before deadline')
