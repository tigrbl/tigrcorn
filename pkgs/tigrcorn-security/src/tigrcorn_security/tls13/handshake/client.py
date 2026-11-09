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

class _QuicTlsClientHandshakeMixin:
    def _handle_server_hello(self, message: ServerHello) -> bytes:
        if self._last_client_hello is None or self._last_client_hello_bytes is None:
            _raise_tls(AlertDescription.INTERNAL_ERROR, 'client hello state is unavailable')
        offered = extension_dict(message.extensions)
        if message.is_hello_retry_request:
            if self._received_hrr:
                _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'received a second HelloRetryRequest')
            selected_version = int(offered.get(ExtensionType.SUPPORTED_VERSIONS, 0))
            if selected_version != 0x0304:
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'HelloRetryRequest selected an invalid TLS version')
            if message.cipher_suite not in self._last_client_hello.cipher_suites:
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'HelloRetryRequest selected an unexpected cipher suite')
            requested_group = offered.get(ExtensionType.KEY_SHARE)
            if not isinstance(requested_group, int) or requested_group not in SUPPORTED_GROUPS:
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'HelloRetryRequest requested an unsupported key share group')
            if message.legacy_session_id_echo != self._last_client_hello.legacy_session_id:
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'HelloRetryRequest echoed the wrong session id')
            self._cookie = offered.get(ExtensionType.COOKIE) if isinstance(offered.get(ExtensionType.COOKIE), bytes) else None
            self._received_hrr = True
            self.early_data_requested = False
            self._configure_cipher_suite(message.cipher_suite)
            self._transcript.reset_with_message_hash(self._last_client_hello_bytes)
            encoded_hrr = message.encode(message_context='hello_retry_request')
            self._hello_retry_request_bytes = encoded_hrr
            self._transcript.append(encoded_hrr)
            self._local_key_share_group = requested_group
            self._local_key_share_private, self._local_key_share_public = _generate_key_share(self._local_key_share_group)
            hello, encoded = self._build_client_hello()
            self._last_client_hello = hello
            self._last_client_hello_bytes = encoded
            self._transcript.append(encoded)
            return encoded

        if int(offered.get(ExtensionType.SUPPORTED_VERSIONS, 0)) != 0x0304:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server selected an invalid TLS version')
        if message.legacy_session_id_echo != self._last_client_hello.legacy_session_id:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'ServerHello echoed the wrong session id')
        if message.cipher_suite not in self._last_client_hello.cipher_suites:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server selected an unexpected cipher suite')
        self._configure_cipher_suite(message.cipher_suite)
        selected_psk = offered.get(ExtensionType.PRE_SHARED_KEY)
        self._using_psk = selected_psk is not None
        if self._using_psk:
            if self.session_ticket is None or int(selected_psk) != 0:
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server selected an unexpected PSK identity')
            if self.session_ticket.cipher_suite != message.cipher_suite:
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server resumed with an unexpected PSK cipher suite')
            self._early_secret = self._key_schedule.make_early_secret(self.session_ticket.resumption_secret)
        else:
            self._early_secret = self._key_schedule.make_early_secret(None)
        key_share = offered.get(ExtensionType.KEY_SHARE)
        if not isinstance(key_share, tuple) or len(key_share) != 2:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server did not supply a valid key share')
        selected_group = int(key_share[0])
        if selected_group != self._local_key_share_group:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server selected an unexpected key share group')
        self._shared_secret = _derive_shared_secret(self._local_key_share_private, selected_group, bytes(key_share[1]))
        encoded = message.encode()
        self._transcript.append(encoded)
        client_hs, server_hs = self._derive_handshake_secrets()
        self._client_handshake_secret = client_hs
        self._server_handshake_secret = server_hs
        return b''

    def _handle_encrypted_extensions(self, message: EncryptedExtensions) -> None:
        offered = extension_dict(message.extensions)
        if offered.get(ExtensionType.EARLY_DATA, False) and (not self.early_data_requested or self._received_hrr):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server accepted early data without a valid client offer')
        peer_transport_parameters = offered.get(ExtensionType.QUIC_TRANSPORT_PARAMETERS)
        if self.transport_mode == 'quic':
            self.peer_transport_parameters = peer_transport_parameters
            if not isinstance(self.peer_transport_parameters, TransportParameters):
                _raise_tls(AlertDescription.MISSING_EXTENSION, 'server did not provide QUIC transport parameters')
        else:
            self.peer_transport_parameters = peer_transport_parameters if isinstance(peer_transport_parameters, TransportParameters) else None
        selected_alpn = offered.get(ExtensionType.ALPN)
        if not isinstance(selected_alpn, str) or selected_alpn not in self.alpns:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'server selected an unexpected ALPN')
        self.selected_alpn = selected_alpn
        self.early_data_accepted = bool(offered.get(ExtensionType.EARLY_DATA, False))
        encoded = message.encode()
        self._transcript.append(encoded)

    def _handle_certificate_request(self, message: CertificateRequest) -> None:
        if self._client_certificate_requested:
            _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'received duplicate CertificateRequest')
        if message.request_context:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'unexpected non-empty CertificateRequest context during handshake')
        offered = extension_dict(message.extensions)
        signature_algorithms = offered.get(ExtensionType.SIGNATURE_ALGORITHMS)
        if not isinstance(signature_algorithms, tuple) or not signature_algorithms:
            _raise_tls(AlertDescription.MISSING_EXTENSION, 'server CertificateRequest did not provide signature_algorithms')
        self._client_certificate_requested = True
        self._client_certificate_request_context = bytes(message.request_context)
        self._certificate_request_signature_algorithms = tuple(int(item) for item in signature_algorithms)
        encoded = message.encode()
        self._transcript.append(encoded)

    def _handle_server_certificate(self, message: Certificate) -> x509.Certificate:
        if not message.certificate_list:
            _raise_tls(AlertDescription.BAD_CERTIFICATE, 'server certificate chain is empty')
        chain = tuple(entry.cert_data for entry in message.certificate_list)
        self.peer_certificate_chain_pem = chain
        encoded = message.encode()
        self._transcript.append(encoded)
        return self._load_selected_peer_certificate()

    def _handle_server_certificate_verify(self, message: CertificateVerify) -> None:
        leaf = self._load_selected_peer_certificate()
        payload = _certificate_verify_input(_SERVER_CERT_VERIFY_CONTEXT, self._current_transcript_hash())
        _verify_with_scheme(leaf.public_key(), message.algorithm, message.signature, payload)
        self._transcript.append(message.encode())

    def _handle_client_certificate(self, message: Certificate) -> None:
        if not self._client_certificate_requested:
            _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'received an unexpected client Certificate message')
        if message.request_context != self._client_certificate_request_context:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'client Certificate request context mismatch')
        self.peer_certificate_chain_pem = tuple(entry.cert_data for entry in message.certificate_list)
        self._peer_certificate_present = bool(self.peer_certificate_chain_pem)
        self._transcript.append(message.encode())
        if self._peer_certificate_present:
            self._load_selected_peer_certificate()

    def _handle_client_certificate_verify(self, message: CertificateVerify) -> None:
        if not self._peer_certificate_present:
            _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'received CertificateVerify without a client certificate')
        leaf = self._load_selected_peer_certificate()
        payload = _certificate_verify_input(_CLIENT_CERT_VERIFY_CONTEXT, self._current_transcript_hash())
        _verify_with_scheme(leaf.public_key(), message.algorithm, message.signature, payload)
        self._transcript.append(message.encode())
        self._peer_certificate_verify_received = True

    def _handle_server_finished(self, message: Finished) -> bytes:
        if self._server_handshake_secret is None:
            _raise_tls(AlertDescription.INTERNAL_ERROR, 'server handshake secret is unavailable')
        if not self._key_schedule.verify_finished(message.verify_data, base_key=self._server_handshake_secret, transcript=self._transcript):
            _raise_tls(AlertDescription.DECRYPT_ERROR, 'server Finished verify_data is invalid')
        encoded = message.encode()
        self._transcript.append(encoded)
        client_ap, server_ap = self._derive_application_secrets()
        self._set_traffic_secrets(
            client_handshake_secret=self._client_handshake_secret,
            server_handshake_secret=self._server_handshake_secret,
            client_application_secret=client_ap,
            server_application_secret=server_ap,
            client_early_secret=getattr(self, '_client_early_secret', None),
        )
        outbound = bytearray()
        if self._client_certificate_requested:
            certificate = Certificate(
                request_context=self._client_certificate_request_context,
                certificate_list=self._certificate_entry_chain() if self._private_key is not None else (),
            )
            encoded_certificate = certificate.encode()
            self._transcript.append(encoded_certificate)
            outbound.extend(encoded_certificate)
            if certificate.certificate_list:
                public_key = self._certificate_chain[0].public_key()
                selected_scheme = _select_certificate_verify_scheme(
                    self._certificate_request_signature_algorithms or SUPPORTED_SIGNATURE_SCHEMES,
                    public_key,
                )
                signature_payload = _certificate_verify_input(_CLIENT_CERT_VERIFY_CONTEXT, self._current_transcript_hash())
                signature = _sign_with_scheme(self._private_key, selected_scheme, signature_payload)
                certificate_verify = CertificateVerify(algorithm=selected_scheme, signature=signature)
                encoded_certificate_verify = certificate_verify.encode()
                self._transcript.append(encoded_certificate_verify)
                outbound.extend(encoded_certificate_verify)
        finished = Finished(verify_data=self._key_schedule.finished_verify_data(self._client_handshake_secret, self._transcript))
        encoded_finished = finished.encode()
        self._transcript.append(encoded_finished)
        outbound.extend(encoded_finished)
        self._finalize_post_handshake_secrets()
        self.complete = True
        self.state = 'complete'
        return bytes(outbound)

    def _handle_new_session_ticket(self, message: NewSessionTicket) -> None:
        if self.transport_mode != 'quic':
            _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'received unexpected NewSessionTicket on stream TLS')
        if self._resumption_master_secret is None or self.selected_alpn is None or self.peer_transport_parameters is None:
            _raise_tls(AlertDescription.UNEXPECTED_MESSAGE, 'received NewSessionTicket before the handshake completed')
        offered = extension_dict(message.extensions)
        max_early_data_size = int(offered.get(ExtensionType.EARLY_DATA, 0) or 0)
        if max_early_data_size not in {0, QUIC_EARLY_DATA_SENTINEL}:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'invalid QUIC early_data sentinel in NewSessionTicket')
        resumption_secret = self._key_schedule.resumption_psk(self._resumption_master_secret, message.ticket_nonce)
        self.received_session_ticket = QuicSessionTicket(
            ticket=message.ticket,
            resumption_secret=resumption_secret,
            server_name=self.server_name,
            alpn=self.selected_alpn,
            transport_parameters=self.peer_transport_parameters,
            ticket_age_add=message.ticket_age_add,
            ticket_nonce=message.ticket_nonce,
            ticket_lifetime=message.ticket_lifetime,
            issued_at=_current_time_ms(),
            cipher_suite=self._selected_cipher_suite,
            max_early_data_size=max_early_data_size,
        )

__all__ = [name for name in globals() if not name.startswith('__')]
