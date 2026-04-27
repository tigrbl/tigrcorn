from .base import TransportDescriptor

TRANSPORTS = {
    "tcp": TransportDescriptor(name="tcp", multiplexed=False),
    "udp": TransportDescriptor(name="udp", multiplexed=False),
    "unix": TransportDescriptor(name="unix", multiplexed=False),
    "pipe": TransportDescriptor(name="pipe", multiplexed=False),
    "inproc": TransportDescriptor(name="inproc", multiplexed=False),
    "quic": TransportDescriptor(name="quic", multiplexed=True),
}
