from __future__ import annotations

from tigrcorn_transports.listeners.inproc import InProcListener
from tigrcorn_transports.listeners.pipe import PipeListener
from tigrcorn_transports.listeners.tcp import TCPListener
from tigrcorn_transports.listeners.udp import UDPListener
from tigrcorn_transports.listeners.unix import UnixListener

LISTENER_TYPES = {
    "tcp": TCPListener,
    "udp": UDPListener,
    "unix": UnixListener,
    "pipe": PipeListener,
    "inproc": InProcListener,
}
