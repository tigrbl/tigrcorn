from __future__ import annotations

import socket

from tigrcorn.protocols.http3 import HTTP3ConnectionCore
from tigrcorn.transports.quic import QuicConnection


def main(host: str = '127.0.0.1', port: int = 8443, *, secret: bytes = b'shared') -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    client = QuicConnection(is_client=True, secret=secret, local_cid=b'adv-http3')
    core = HTTP3ConnectionCore(role='client')
    try:
        sock.sendto(client.build_initial(), (host, port))
        for _ in range(4):
            data, _addr = sock.recvfrom(65535)
            for event in client.receive_datagram(data):
                if event.kind == 'stream':
                    core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        request_stream_id = 0
        request_payload = core.get_request(request_stream_id).encode_request(
            [
                (b':method', b'GET'),
                (b':scheme', b'https'),
                (b':path', b'/early-hints'),
                (b':authority', b'localhost'),
            ]
        )
        sock.sendto(client.send_stream_data(request_stream_id, request_payload, fin=True), (host, port))
        response_state = None
        while response_state is None or not response_state.ended:
            data, _addr = sock.recvfrom(65535)
            for event in client.receive_datagram(data):
                if event.kind == 'stream' and event.stream_id == request_stream_id:
                    response_state = core.receive_stream_data(event.stream_id, event.data, fin=event.fin)
        assert response_state is not None
        print('informational:', response_state.informational_headers)
        print('final headers:', response_state.headers)
        print('body:', response_state.body.decode('utf-8'))
    finally:
        sock.close()


if __name__ == '__main__':  # pragma: no cover
    main()
