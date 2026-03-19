from __future__ import annotations

import json
import os
import signal
import socket
import sys

STOP = False



def _handle_signal(_signum, _frame) -> None:
    global STOP
    STOP = True



def _write_json(path_env: str, payload: dict) -> None:
    path = os.environ.get(path_env)
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle)



def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if '--version' in argv:
        print('interop-udp-echo-server 1.0')
        return 0
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    bind_host = os.environ['INTEROP_BIND_HOST']
    bind_port = int(os.environ['INTEROP_BIND_PORT'])
    family = socket.AF_INET6 if ':' in bind_host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    if family == socket.AF_INET6:
        sock.bind((bind_host, bind_port, 0, 0))
    else:
        sock.bind((bind_host, bind_port))
    sock.settimeout(0.2)
    print('READY', flush=True)
    transcript = {'received': 0, 'echoed': 0}
    try:
        while not STOP:
            try:
                data, addr = sock.recvfrom(65535)
            except TimeoutError:
                continue
            transcript['received'] += 1
            transcript['echoed'] += 1
            transcript['last_length'] = len(data)
            sock.sendto(data, addr)
            _write_json('INTEROP_TRANSCRIPT_PATH', transcript)
    finally:
        sock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
