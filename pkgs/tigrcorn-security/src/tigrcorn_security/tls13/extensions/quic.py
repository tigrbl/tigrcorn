from __future__ import annotations

from .imports import *
from .models import *

def encode_quic_transport_parameters(parameters: TransportParameters) -> bytes:
    return parameters.to_bytes()



def decode_quic_transport_parameters(data: bytes) -> TransportParameters:
    return TransportParameters.from_bytes(data)

__all__ = [name for name in globals() if not name.startswith('__')]
