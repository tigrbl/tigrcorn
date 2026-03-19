from __future__ import annotations

import json
import os
import socket
import sys

from tigrcorn.transports.quic.packets import QuicLongHeaderPacket, QuicLongHeaderType



def _write_json(path_env: str, payload: dict) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)



def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if '--version' in argv:
        print('interop-quic-client 1.0')
        return 0
    host = os.environ['INTEROP_TARGET_HOST']
    port = int(os.environ['INTEROP_TARGET_PORT'])
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    packet = QuicLongHeaderPacket(
        packet_type=QuicLongHeaderType.INITIAL,
        version=1,
        destination_connection_id=b'cli01234',
        source_connection_id=b'srv05678',
        token=b'',
        packet_number=b'\x01',
        payload=b'quic-observer-test',
    ).encode()
    sock.sendto(packet, (host, port))
    response, _addr = sock.recvfrom(65535)
    transcript = {'request_bytes': len(packet), 'response_bytes': len(response)}
    negotiation = {'alpn': 'h3', 'version': 1, 'transport_parameters': {'max_udp_payload_size': 1200}}
    _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    _write_json('INTEROP_NEGOTIATION_PATH', negotiation)
    print(json.dumps(transcript, sort_keys=True))
    return 0 if response == packet else 1


if __name__ == '__main__':
    raise SystemExit(main())
