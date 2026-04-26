from __future__ import annotations

from tigrcorn.listeners.inproc import InProcListener
from tigrcorn.listeners.pipe import PipeListener
from tigrcorn.listeners.tcp import TCPListener
from tigrcorn.listeners.udp import UDPListener
from tigrcorn.listeners.unix import UnixListener

LISTENER_TYPES = {
    "tcp": TCPListener,
    "udp": UDPListener,
    "unix": UnixListener,
    "pipe": PipeListener,
    "inproc": InProcListener,
}
