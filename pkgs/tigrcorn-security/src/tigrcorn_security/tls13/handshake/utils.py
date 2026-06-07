from __future__ import annotations

from .imports import *
from .alerts import *

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')



def _unb64(data: str) -> bytes:
    return base64.b64decode(data.encode('ascii'))



def _raise_tls(description: int, message: str) -> None:
    raise TlsAlertError(description, message)



def _raise_quic_transport(error_code: int, message: str) -> None:
    raise QuicTransportError(error_code, message)



def _select_alpn(client_alpns: Sequence[str], server_alpns: Sequence[str]) -> str:
    for alpn in client_alpns:
        if alpn in server_alpns:
            return alpn
    _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'ALPN negotiation failed')



def _certificate_verify_input(context: bytes, transcript_hash: bytes) -> bytes:
    return (b' ' * 64) + context + b'\x00' + transcript_hash



def _current_time_ms() -> int:
    return int(time.time() * 1000)

__all__ = [name for name in globals() if not name.startswith('__')]
