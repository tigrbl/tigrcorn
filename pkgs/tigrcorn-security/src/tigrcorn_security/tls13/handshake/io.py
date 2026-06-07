from __future__ import annotations

from .imports import *
from .alerts import *
from .models import *
from .replay import *
from .utils import *
from .signatures import *
from .key_exchange import *
from .tickets import *
from .certificates import *

class _QuicTlsMessageIoMixin:
    def receive(self, data: bytes) -> bytes:
        self._receive_buffer.extend(data)
        outbound = bytearray()
        pending_leaf: x509.Certificate | None = None
        while self._receive_buffer:
            raw_view = bytes(self._receive_buffer)
            try:
                message, consumed = decode_handshake_message(raw_view, 0)
            except NeedMoreData:
                break
            raw_message = raw_view[:consumed]
            del self._receive_buffer[:consumed]
            if isinstance(message, KeyUpdate):
                _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'TLS KeyUpdate is not used with QUIC')
            if self.is_client:
                if isinstance(message, ServerHello):
                    outbound.extend(self._handle_server_hello(message))
                    continue
                if isinstance(message, EncryptedExtensions):
                    self._handle_encrypted_extensions(message)
                    continue
                if isinstance(message, CertificateRequest):
                    self._handle_certificate_request(message)
                    continue
                if isinstance(message, Certificate):
                    pending_leaf = self._handle_server_certificate(message)
                    continue
                if isinstance(message, CertificateVerify):
                    if pending_leaf is None:
                        pending_leaf = self._load_selected_peer_certificate()
                    self._handle_server_certificate_verify(message)
                    continue
                if isinstance(message, Finished):
                    outbound.extend(self._handle_server_finished(message))
                    continue
                if isinstance(message, NewSessionTicket):
                    self._handle_new_session_ticket(message)
                    continue
                _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'unexpected handshake message received by client')
            else:
                if isinstance(message, ClientHello):
                    outbound.extend(self._handle_client_hello(message, raw_message=raw_message))
                    continue
                if isinstance(message, Certificate):
                    self._handle_client_certificate(message)
                    continue
                if isinstance(message, CertificateVerify):
                    self._handle_client_certificate_verify(message)
                    continue
                if isinstance(message, Finished):
                    outbound.extend(self._handle_client_finished(message))
                    continue
                _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'unexpected handshake message received by server')
        return bytes(outbound)

    def issue_session_ticket(self, *, max_early_data_size: int = 0) -> bytes:
        if self.transport_mode != 'quic':
            raise ProtocolError('session tickets are not exposed on the stream TLS path')
        if not self.complete or self._resumption_master_secret is None or self.selected_alpn is None:
            raise ProtocolError('handshake must complete before issuing a session ticket')
        ticket_lifetime = _MAX_TICKET_LIFETIME_SECONDS
        ticket_age_add = int.from_bytes(os.urandom(4), 'big')
        ticket_nonce = os.urandom(8)
        early_data_value = QUIC_EARLY_DATA_SENTINEL if max_early_data_size else 0
        resumption_secret = self._key_schedule.resumption_psk(self._resumption_master_secret, ticket_nonce)
        payload = {
            'v': 2,
            'i': _current_time_ms(),
            'l': ticket_lifetime,
            'a': ticket_age_add,
            'n': _b64(ticket_nonce),
            's': self.server_name,
            'h': self.selected_alpn,
            'p': _b64(self.transport_parameters.to_bytes()),
            'c': self._selected_cipher_suite,
            'r': _b64(resumption_secret),
            'e': early_data_value,
        }
        opaque_ticket = _seal_ticket(self._ticket_key, payload)
        ticket = QuicSessionTicket(
            ticket=opaque_ticket,
            resumption_secret=resumption_secret,
            server_name=self.server_name,
            alpn=self.selected_alpn,
            transport_parameters=self.transport_parameters,
            ticket_age_add=ticket_age_add,
            ticket_nonce=ticket_nonce,
            ticket_lifetime=ticket_lifetime,
            issued_at=int(payload['i']),
            cipher_suite=self._selected_cipher_suite,
            max_early_data_size=early_data_value,
        )
        self.issued_session_ticket = ticket
        extensions: list[TlsExtension] = []
        if early_data_value:
            extensions.append(TlsExtension(ExtensionType.EARLY_DATA, early_data_value))
        message = NewSessionTicket(
            ticket_lifetime=ticket_lifetime,
            ticket_age_add=ticket_age_add,
            ticket_nonce=ticket_nonce,
            ticket=opaque_ticket,
            extensions=tuple(extensions),
        )
        return message.encode()


TLS13_HANDSHAKE_STATE_TABLE: tuple[dict[str, object], ...] = (
    {
        'from': 'client_idle',
        'event': 'start() / outbound ClientHello',
        'to': 'client_wait_server',
        'notes': 'client has emitted ClientHello and waits for the server flight',
    },
    {
        'from': 'server_idle',
        'event': 'ClientHello accepted without HRR',
        'to': 'server_wait_client_finished',
        'notes': 'server selected parameters and waits for the client Finished',
    },
    {
        'from': 'server_idle',
        'event': 'ClientHello requires HRR',
        'to': 'server_wait_client_hello_retry',
        'notes': 'server issued HelloRetryRequest and waits for a replacement ClientHello',
    },
    {
        'from': 'server_wait_client_hello_retry',
        'event': 'replacement ClientHello accepted',
        'to': 'server_wait_client_finished',
        'notes': 'retry path converges on the same post-ServerHello wait state',
    },
    {
        'from': 'client_wait_server',
        'event': 'server flight validated and Finished processed',
        'to': 'complete',
        'notes': 'client completed certificate verification, Finished, and traffic secret installation',
    },
    {
        'from': 'server_wait_client_finished',
        'event': 'client Finished validated',
        'to': 'complete',
        'notes': 'server completed handshake and may issue session tickets',
    },
)

__all__ = [name for name in globals() if not name.startswith('__')]
