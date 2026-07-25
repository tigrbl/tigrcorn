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

class _QuicTlsServerHandshakeMixin:
    def _handle_client_hello(self, message: ClientHello, *, raw_message: bytes | None = None) -> bytes:
        encoded_client_hello = raw_message if raw_message is not None else message.encode()
        extension_types = [int(extension.extension_type) for extension in message.extensions]
        if ExtensionType.PRE_SHARED_KEY in extension_types and extension_types[-1] != ExtensionType.PRE_SHARED_KEY:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'pre_shared_key must be the final ClientHello extension')
        if ExtensionType.EARLY_DATA in extension_types and ExtensionType.PRE_SHARED_KEY not in extension_types:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'early_data requires a matching pre_shared_key offer')
        if self.transport_mode == 'quic' and message.legacy_session_id:
            _raise_quic_transport(
                _QUIC_TRANSPORT_ERROR_PROTOCOL_VIOLATION,
                'QUIC clients must not use TLS middlebox compatibility mode',
            )
        offered = extension_dict(message.extensions)
        versions = tuple(int(version) for version in offered.get(ExtensionType.SUPPORTED_VERSIONS, ()))
        if 0x0304 not in versions:
            _raise_tls(AlertDescription.PROTOCOL_VERSION, 'client did not offer TLS 1.3')
        selected_cipher_suite = _select_cipher_suite(message.cipher_suites, self.supported_cipher_suites)
        if selected_cipher_suite is None:
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'client did not offer a mutually supported TLS 1.3 cipher suite')
        self._configure_cipher_suite(selected_cipher_suite)
        offered_alpns = tuple(str(item) for item in offered.get(ExtensionType.ALPN, ()))
        self.selected_alpn = _select_alpn(offered_alpns, self.alpns)
        peer_transport_parameters = offered.get(ExtensionType.QUIC_TRANSPORT_PARAMETERS)
        if self.transport_mode == 'quic':
            self.peer_transport_parameters = peer_transport_parameters
            if not isinstance(self.peer_transport_parameters, TransportParameters):
                _raise_tls(AlertDescription.MISSING_EXTENSION, 'client did not provide QUIC transport parameters')
        else:
            self.peer_transport_parameters = peer_transport_parameters if isinstance(peer_transport_parameters, TransportParameters) else None
        peer_signature_algorithms = offered.get(ExtensionType.SIGNATURE_ALGORITHMS)
        if not isinstance(peer_signature_algorithms, tuple) or not peer_signature_algorithms:
            _raise_tls(AlertDescription.MISSING_EXTENSION, 'client did not provide signature_algorithms')
        self._peer_signature_algorithms = tuple(int(item) for item in peer_signature_algorithms)
        peer_certificate_algorithms = offered.get(ExtensionType.SIGNATURE_ALGORITHMS_CERT, peer_signature_algorithms)
        if not isinstance(peer_certificate_algorithms, tuple) or not peer_certificate_algorithms:
            _raise_tls(AlertDescription.MISSING_EXTENSION, 'client did not provide certificate signature algorithms')
        self._peer_certificate_signature_algorithms = tuple(int(item) for item in peer_certificate_algorithms)
        supported_groups = tuple(int(group) for group in offered.get(ExtensionType.SUPPORTED_GROUPS, ()))
        key_shares = offered.get(ExtensionType.KEY_SHARE)
        if not isinstance(key_shares, dict):
            key_shares = {}

        selected_group: int | None
        if self.state == 'server_wait_client_hello_retry':
            if self._hrr_requested_group is None:
                _raise_tls(AlertDescription.INTERNAL_ERROR, 'HelloRetryRequest state is unavailable')
            if self._hrr_requested_group not in key_shares:
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'client did not supply the requested key share after HelloRetryRequest')
            selected_group = self._hrr_requested_group
        else:
            selected_group = None
            for group in SUPPORTED_GROUPS:
                if group in key_shares:
                    selected_group = group
                    break
            if selected_group is None:
                requested_group = _preferred_supported_group(supported_groups=supported_groups, key_shares=key_shares)
                if requested_group is None:
                    _raise_tls(AlertDescription.HANDSHAKE_FAILURE, 'client does not support a mutually compatible key exchange group')
                hrr = ServerHello(
                    random=HELLO_RETRY_REQUEST_RANDOM,
                    legacy_session_id_echo=message.legacy_session_id,
                    cipher_suite=selected_cipher_suite,
                    extensions=(
                        TlsExtension(ExtensionType.SUPPORTED_VERSIONS, 0x0304),
                        TlsExtension(ExtensionType.KEY_SHARE, requested_group),
                    ),
                )
                encoded_hrr = hrr.encode(message_context='hello_retry_request')
                self._configure_cipher_suite(selected_cipher_suite)
                if self._last_client_hello_bytes is not None:
                    self._transcript.reset_with_message_hash(self._last_client_hello_bytes)
                else:
                    self._transcript.reset_with_message_hash(message.encode())
                self._transcript.append(encoded_hrr)
                self._hello_retry_request_bytes = encoded_hrr
                self._received_hrr = True
                self._hrr_requested_group = requested_group
                self.early_data_accepted = False
                self.state = 'server_wait_client_hello_retry'
                return encoded_hrr

        offered_psks = offered.get(ExtensionType.PRE_SHARED_KEY)
        psk_modes = tuple(int(item) for item in offered.get(ExtensionType.PSK_KEY_EXCHANGE_MODES, ()))
        client_requested_early_data = bool(offered.get(ExtensionType.EARLY_DATA, False))
        self._using_psk = False
        self._selected_psk_index = None
        self._selected_psk_ticket = None
        if isinstance(offered_psks, OfferedPsks) and PSK_MODE_DHE_KE in psk_modes:
            if raw_message is not None:
                truncated_bytes = _client_hello_without_binders(raw_message, offered_psks.binders)
            else:
                truncated_extensions: list[TlsExtension] = []
                for extension in message.extensions:
                    if int(extension.extension_type) == ExtensionType.PRE_SHARED_KEY:
                        truncated_extensions.append(
                            TlsExtension(
                                ExtensionType.PRE_SHARED_KEY,
                                extension.value,
                                raw_data=encode_pre_shared_key_client_without_binders(offered_psks.identities),
                            )
                        )
                    else:
                        truncated_extensions.append(extension)
                truncated_message = message.with_extensions(tuple(truncated_extensions))
                truncated_bytes = truncated_message.encode()
            transcript_hash = self._transcript.digest_with(truncated_bytes)
            now_ms = _current_time_ms()
            for index, (identity, binder) in enumerate(zip(offered_psks.identities, offered_psks.binders)):
                try:
                    payload = _open_ticket(self._ticket_key, identity.identity)
                except TlsAlertError:
                    continue
                ticket = _session_ticket_from_payload(payload, opaque_ticket=identity.identity)
                if ticket.server_name != self.server_name:
                    continue
                if ticket.alpn not in offered_alpns:
                    continue
                if ticket.cipher_suite != selected_cipher_suite:
                    continue
                age_ms = (identity.obfuscated_ticket_age - ticket.ticket_age_add) % (2**32)
                actual_age_ms = max(now_ms - ticket.issued_at, 0)
                if actual_age_ms > (ticket.ticket_lifetime * 1000):
                    continue
                if abs(int(actual_age_ms) - int(age_ms)) > _MAX_AGE_SKEW_MS:
                    continue
                early_secret = self._key_schedule.make_early_secret(ticket.resumption_secret)
                binder_key = self._key_schedule.make_binder_key(early_secret)
                expected_binder = hmac.new(
                    self._key_schedule.finished_key(binder_key),
                    transcript_hash,
                    getattr(hashlib, self._key_schedule.hash_name),
                ).digest()
                if not hmac.compare_digest(expected_binder, binder):
                    continue
                self._using_psk = True
                self._selected_psk_index = index
                self._selected_psk_ticket = ticket
                self._early_secret = early_secret
                self._client_early_secret = self._key_schedule.client_early_traffic_secret(early_secret, encoded_client_hello)
                if (
                    self.transport_mode == 'quic'
                    and client_requested_early_data
                    and index == 0
                    and self.enable_early_data
                    and ticket.max_early_data_size == QUIC_EARLY_DATA_SENTINEL
                    and ticket.transport_parameters.is_0rtt_compatible_with(self.transport_parameters)
                    and _claim_ticket_for_0rtt(ticket.ticket, now_ms=now_ms, ticket_lifetime=ticket.ticket_lifetime)
                ):
                    self.early_data_accepted = True
                else:
                    self.early_data_accepted = False
                break
        if not self._using_psk:
            self._early_secret = self._key_schedule.make_early_secret(None)
            self._client_early_secret = None
            self.early_data_accepted = False

        self._last_client_hello = message
        self._last_client_hello_bytes = encoded_client_hello
        self._transcript.append(self._last_client_hello_bytes)

        assert selected_group is not None
        if self._local_key_share_group != selected_group:
            self._local_key_share_group = selected_group
            self._local_key_share_private, self._local_key_share_public = _generate_key_share(selected_group)
        self._shared_secret = _derive_shared_secret(self._local_key_share_private, selected_group, key_shares[selected_group])

        server_hello_extensions: list[TlsExtension] = [
            TlsExtension(ExtensionType.SUPPORTED_VERSIONS, 0x0304),
            TlsExtension(ExtensionType.KEY_SHARE, (selected_group, self._local_key_share_public)),
        ]
        if self._using_psk and self._selected_psk_index is not None:
            server_hello_extensions.append(TlsExtension(ExtensionType.PRE_SHARED_KEY, self._selected_psk_index))
        server_hello = ServerHello(
            random=os.urandom(32),
            legacy_session_id_echo=message.legacy_session_id,
            cipher_suite=selected_cipher_suite,
            extensions=tuple(server_hello_extensions),
        )
        encoded_server_hello = server_hello.encode()
        self._transcript.append(encoded_server_hello)
        client_hs, server_hs = self._derive_handshake_secrets()

        ee_extensions = [
            TlsExtension(ExtensionType.ALPN, self.selected_alpn),
        ]
        if self.transport_mode == 'quic':
            ee_extensions.append(TlsExtension(ExtensionType.QUIC_TRANSPORT_PARAMETERS, self.transport_parameters))
        if self.early_data_accepted:
            ee_extensions.append(TlsExtension(ExtensionType.EARLY_DATA, True))
        encrypted_extensions = EncryptedExtensions(extensions=tuple(ee_extensions))
        encoded_ee = encrypted_extensions.encode()
        self._transcript.append(encoded_ee)

        flight = bytearray(encoded_server_hello)
        flight.extend(encoded_ee)
        if self.require_client_certificate:
            certificate_request = CertificateRequest(
                request_context=b'',
                extensions=(
                    TlsExtension(ExtensionType.SIGNATURE_ALGORITHMS, SUPPORTED_SIGNATURE_SCHEMES),
                    TlsExtension(ExtensionType.SIGNATURE_ALGORITHMS_CERT, SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES),
                ),
            )
            encoded_certificate_request = certificate_request.encode()
            self._transcript.append(encoded_certificate_request)
            flight.extend(encoded_certificate_request)
            self._client_certificate_requested = True
            self._client_certificate_request_context = b''
        if not self._using_psk:
            certificate = Certificate(certificate_list=self._certificate_entry_chain())
            encoded_certificate = certificate.encode()
            self._transcript.append(encoded_certificate)
            flight.extend(encoded_certificate)
            public_key = self._certificate_chain[0].public_key()
            selected_scheme = _select_certificate_verify_scheme(self._peer_signature_algorithms, public_key)
            signature_payload = _certificate_verify_input(_SERVER_CERT_VERIFY_CONTEXT, self._current_transcript_hash())
            signature = _sign_with_scheme(self._private_key, selected_scheme, signature_payload)
            certificate_verify = CertificateVerify(algorithm=selected_scheme, signature=signature)
            encoded_cv = certificate_verify.encode()
            self._transcript.append(encoded_cv)
            flight.extend(encoded_cv)

        finished = Finished(verify_data=self._key_schedule.finished_verify_data(server_hs, self._transcript))
        encoded_finished = finished.encode()
        self._transcript.append(encoded_finished)
        flight.extend(encoded_finished)
        client_ap, server_ap = self._derive_application_secrets()
        client_early = getattr(self, '_client_early_secret', None)
        self._set_traffic_secrets(
            client_handshake_secret=client_hs,
            server_handshake_secret=server_hs,
            client_application_secret=client_ap,
            server_application_secret=server_ap,
            client_early_secret=client_early,
        )
        self.state = 'server_wait_client_finished'
        return bytes(flight)

    def _handle_client_finished(self, message: Finished) -> bytes:
        if self.require_client_certificate:
            if not self.peer_certificate_chain_pem:
                _raise_tls(AlertDescription.CERTIFICATE_REQUIRED, 'client certificate is required')
            if not self._peer_certificate_verify_received:
                _raise_tls(AlertDescription.HANDSHAKE_FAILURE, 'client CertificateVerify is missing')
        if self._client_handshake_secret is None:
            _raise_tls(AlertDescription.INTERNAL_ERROR, 'client handshake secret is unavailable')
        if not self._key_schedule.verify_finished(message.verify_data, base_key=self._client_handshake_secret, transcript=self._transcript):
            _raise_tls(AlertDescription.DECRYPT_ERROR, 'client Finished verify_data is invalid')
        self._transcript.append(message.encode())
        self._finalize_post_handshake_secrets()
        self.complete = True
        self.state = 'complete'
        return b''

__all__ = [name for name in globals() if not name.startswith('__')]
