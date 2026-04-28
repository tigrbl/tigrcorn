from __future__ import annotations

import socket


def configure_udp_socket(sock) -> None:
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError:
        pass
