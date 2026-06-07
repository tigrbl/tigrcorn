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

class _QuicTlsHandshakeBase:
    def __init__(
        self,
        *,
        is_client: bool,
        alpn: str | Sequence[str] = 'h3',
        server_name: str = 'localhost',
        transport_parameters: TransportParameters | None = None,
        certificate_pem: bytes | None = None,
        private_key_pem: bytes | None = None,
        private_key_password: bytes | None = None,
        trusted_certificates: Iterable[bytes] | None = None,
        require_client_certificate: bool = False,
        session_ticket: QuicSessionTicket | bytes | None = None,
        enable_early_data: bool = False,
        transport_mode: str = 'quic',
        validation_policy: CertificateValidationPolicy | None = None,
        cipher_suites: Sequence[int] | None = None,
    ) -> None:
        self.is_client = is_client
        if isinstance(alpn, str):
            self.alpns = (alpn,)
        else:
            offered = tuple(alpn)
            if not offered:
                raise ValueError('at least one ALPN identifier is required')
            self.alpns = offered
        self.alpn = self.alpns[0]
        if transport_mode not in {'quic', 'stream'}:
            raise ValueError(f'unsupported TLS transport_mode: {transport_mode!r}')
        self.transport_mode = transport_mode
        self.server_name = server_name
        self.transport_parameters = transport_parameters or (TransportParameters() if transport_mode == 'quic' else None)
        self.validation_policy = validation_policy
        configured_cipher_suites = tuple(int(item) for item in (cipher_suites or SUPPORTED_CIPHER_SUITES))
        if not configured_cipher_suites:
            raise ValueError('at least one TLS 1.3 cipher suite must be configured')
        unsupported_cipher_suites = [item for item in configured_cipher_suites if item not in SUPPORTED_CIPHER_SUITES]
        if unsupported_cipher_suites:
            raise ValueError(f'unsupported TLS 1.3 cipher suites: {unsupported_cipher_suites!r}')
        self.supported_cipher_suites = configured_cipher_suites
        if not is_client and (certificate_pem is None or private_key_pem is None):
            certificate_pem, private_key_pem = generate_self_signed_certificate(server_name)
        if isinstance(session_ticket, bytes):
            self.session_ticket = QuicSessionTicket.deserialize(session_ticket)
        else:
            self.session_ticket = session_ticket
        self.certificate_pem = certificate_pem
        self.private_key_pem = private_key_pem
        self.trusted_certificates = tuple(trusted_certificates or ())
        self.require_client_certificate = bool(require_client_certificate)
        if not self.is_client and self.require_client_certificate and not self.trusted_certificates:
            raise ValueError('trusted_certificates are required when client certificates are mandatory')
        if self.transport_mode == 'stream':
            self.enable_early_data = False
        self._private_key = serialization.load_pem_private_key(private_key_pem, password=private_key_password) if private_key_pem is not None else None
        if certificate_pem is not None:
            self._certificate_chain = tuple(load_pem_certificates((certificate_pem,)))
            self._certificate_chain_pem = tuple(
                certificate.public_bytes(serialization.Encoding.PEM) for certificate in self._certificate_chain
            )
        else:
            self._certificate_chain = ()
            self._certificate_chain_pem = ()
        self._certificate_chain_der = tuple(certificate.public_bytes(serialization.Encoding.DER) for certificate in self._certificate_chain)
        self._ticket_key = _ticket_protection_key(private_key_pem, certificate_pem)
        self.enable_early_data = enable_early_data and self.transport_mode == 'quic'
        self.early_data_requested = bool(self.session_ticket and self.enable_early_data and is_client)
        self.early_data_accepted = False
        self.issued_session_ticket: QuicSessionTicket | None = None
        self.received_session_ticket: QuicSessionTicket | None = None
        self.selected_alpn: str | None = None
        self.peer_transport_parameters: TransportParameters | None = None
        self.peer_certificate_pem: bytes | None = None
        self.peer_certificate_chain_pem: tuple[bytes, ...] = ()
        self.complete = False
        self.state = 'client_idle' if is_client else 'server_idle'

        initial_cipher_suite = (
            self.session_ticket.cipher_suite
            if (
                self.session_ticket is not None
                and self.session_ticket.cipher_suite in self.supported_cipher_suites
            )
            else self.supported_cipher_suites[0]
        )
        self._selected_cipher_suite = int(initial_cipher_suite)
        self._cipher_parameters = cipher_suite_parameters(self._selected_cipher_suite)
        self._key_schedule = Tls13KeySchedule(hash_name=self._cipher_parameters.hash_name)
        self._transcript = HandshakeTranscript(hash_name=self._cipher_parameters.hash_name)
        self._receive_buffer = bytearray()
        self._local_key_share_group = GROUP_X25519
        self._local_key_share_private, self._local_key_share_public = _generate_key_share(self._local_key_share_group)
        self._last_client_hello: ClientHello | None = None
        self._last_client_hello_bytes: bytes | None = None
        self._hello_retry_request_bytes: bytes | None = None
        self._received_hrr = False
        self._hrr_requested_group: int | None = None
        self._cookie: bytes | None = None
        self._client_certificate_requested = False
        self._client_certificate_request_context = b''
        self._certificate_request_signature_algorithms: tuple[int, ...] = ()
        self._peer_signature_algorithms: tuple[int, ...] = SUPPORTED_SIGNATURE_SCHEMES
        self._peer_certificate_signature_algorithms: tuple[int, ...] = SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES
        self._using_psk = False
        self._selected_psk_index: int | None = None
        self._selected_psk_ticket: QuicSessionTicket | None = None
        self._peer_certificate_present = False
        self._peer_certificate_verify_received = False
        self._shared_secret: bytes | None = None
        self._early_secret: bytes | None = None
        self._client_early_secret: bytes | None = None
        self._master_secret: bytes | None = None
        self._traffic_secrets: QuicTrafficSecrets | None = None
        self._client_handshake_secret: bytes | None = None
        self._server_handshake_secret: bytes | None = None
        self._resumption_master_secret: bytes | None = None
        self._exporter_master_secret: bytes | None = None

    @property
    def traffic_secrets(self) -> QuicTrafficSecrets | None:
        return self._traffic_secrets

    @property
    def cipher_parameters(self) -> CipherSuiteParameters:
        return self._cipher_parameters

    def packet_protection_parameters(self, *, stage: str) -> CipherSuiteParameters:
        if stage == '0rtt':
            if self._selected_psk_ticket is not None:
                return cipher_suite_parameters(self._selected_psk_ticket.cipher_suite)
            if self.session_ticket is not None:
                return cipher_suite_parameters(self.session_ticket.cipher_suite)
        return self._cipher_parameters

    def _configure_cipher_suite(self, cipher_suite: int) -> None:
        parameters = cipher_suite_parameters(cipher_suite)
        self._selected_cipher_suite = int(cipher_suite)
        self._cipher_parameters = parameters
        self._key_schedule = Tls13KeySchedule(hash_name=parameters.hash_name)
        self._transcript.hash_name = parameters.hash_name

    def outbound_flights(self, data: bytes) -> list[HandshakeFlight]:
        return [HandshakeFlight(packet_space=flight.packet_space, data=flight.data) for flight in split_handshake_flights(data)]

    def _current_transcript_hash(self) -> bytes:
        return self._transcript.digest()

    def _set_traffic_secrets(
        self,
        *,
        client_handshake_secret: bytes,
        server_handshake_secret: bytes,
        client_application_secret: bytes,
        server_application_secret: bytes,
        client_early_secret: bytes | None,
    ) -> None:
        self._client_handshake_secret = client_handshake_secret
        self._server_handshake_secret = server_handshake_secret
        self._traffic_secrets = QuicTrafficSecrets(
            client_handshake_secret=client_handshake_secret,
            server_handshake_secret=server_handshake_secret,
            client_application_secret=client_application_secret,
            server_application_secret=server_application_secret,
            client_early_secret=client_early_secret,
            exporter_master_secret=self._exporter_master_secret,
            resumption_master_secret=self._resumption_master_secret,
        )

    def _server_base_key(self) -> bytes:
        if self._server_handshake_secret is None:
            _raise_tls(AlertDescription.INTERNAL_ERROR, 'server handshake secret is not available')
        return self._server_handshake_secret

    def _client_base_key(self) -> bytes:
        if self._client_handshake_secret is None:
            _raise_tls(AlertDescription.INTERNAL_ERROR, 'client handshake secret is not available')
        return self._client_handshake_secret

    def _certificate_entry_chain(self) -> tuple[CertificateEntry, ...]:
        return tuple(CertificateEntry(cert_data=certificate_der) for certificate_der in self._certificate_chain_der)

    def _build_client_hello(self) -> tuple[ClientHello, bytes]:
        base_extensions: list[TlsExtension] = [
            TlsExtension(ExtensionType.SERVER_NAME, self.server_name),
            TlsExtension(ExtensionType.SUPPORTED_VERSIONS, (0x0304,)),
            TlsExtension(ExtensionType.SUPPORTED_GROUPS, SUPPORTED_GROUPS),
            TlsExtension(ExtensionType.SIGNATURE_ALGORITHMS, SUPPORTED_SIGNATURE_SCHEMES),
            TlsExtension(ExtensionType.SIGNATURE_ALGORITHMS_CERT, SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES),
            TlsExtension(ExtensionType.ALPN, self.alpns),
            TlsExtension(ExtensionType.KEY_SHARE, ((self._local_key_share_group, self._local_key_share_public),)),
        ]
        if self.transport_mode == 'quic':
            base_extensions.append(TlsExtension(ExtensionType.QUIC_TRANSPORT_PARAMETERS, self.transport_parameters))
        if self._cookie is not None:
            base_extensions.append(TlsExtension(ExtensionType.COOKIE, self._cookie))

        offered_psks: OfferedPsks | None = None
        if self.session_ticket is not None:
            age_ms = max(_current_time_ms() - self.session_ticket.issued_at, 0)
            identity = PskIdentity(
                identity=self.session_ticket.ticket,
                obfuscated_ticket_age=(age_ms + self.session_ticket.ticket_age_add) % (2**32),
            )
            offered_psks = OfferedPsks(identities=(identity,), binders=(b'\x00' * self._key_schedule.hash_length,))
            base_extensions.append(TlsExtension(ExtensionType.PSK_KEY_EXCHANGE_MODES, (PSK_MODE_DHE_KE,)))
            if self.early_data_requested and not self._received_hrr:
                base_extensions.append(TlsExtension(ExtensionType.EARLY_DATA, True))

        hello = ClientHello(
            random=os.urandom(32),
            legacy_session_id=b'' if self.transport_mode == 'quic' else os.urandom(32),
            cipher_suites=self.supported_cipher_suites,
            extensions=tuple(base_extensions),
        )

        if offered_psks is None:
            encoded = hello.encode()
            return hello, encoded

        psk_extension = TlsExtension(ExtensionType.PRE_SHARED_KEY, offered_psks)
        hello_with_placeholder = hello.with_extensions(tuple(base_extensions) + (psk_extension,))
        placeholder_bytes = hello_with_placeholder.encode()
        truncated_bytes = _client_hello_without_binders(placeholder_bytes, offered_psks.binders)
        early_secret = self._key_schedule.make_early_secret(self.session_ticket.resumption_secret)
        binder_key = self._key_schedule.make_binder_key(early_secret)
        transcript_hash = self._transcript.digest_with(truncated_bytes)
        binder = hmac.new(
            self._key_schedule.finished_key(binder_key),
            transcript_hash,
            getattr(hashlib, self._key_schedule.hash_name),
        ).digest()
        final_psk = TlsExtension(
            ExtensionType.PRE_SHARED_KEY,
            OfferedPsks(identities=offered_psks.identities, binders=(binder,)),
        )
        final_hello = hello.with_extensions(tuple(base_extensions) + (final_psk,))
        encoded = final_hello.encode()
        self._early_secret = early_secret
        self._client_early_secret = self._key_schedule.client_early_traffic_secret(early_secret, encoded)
        return final_hello, encoded

    def initiate(self) -> bytes:
        if not self.is_client:
            raise ProtocolError('only a client can initiate the handshake')
        if self.state not in {'client_idle', 'client_wait_server'}:
            raise ProtocolError('unexpected client handshake state')
        hello, encoded = self._build_client_hello()
        self._last_client_hello = hello
        self._last_client_hello_bytes = encoded
        self._transcript.append(encoded)
        self.state = 'client_wait_server'
        return encoded

    def _derive_handshake_secrets(self) -> tuple[bytes, bytes]:
        if self._shared_secret is None:
            _raise_tls(AlertDescription.INTERNAL_ERROR, 'shared secret is not available')
        if self._early_secret is None:
            self._early_secret = self._key_schedule.make_early_secret(None)
        handshake_secret = self._key_schedule.handshake_secret(self._early_secret, self._shared_secret)
        return self._key_schedule.handshake_traffic_secrets(handshake_secret, self._transcript)

    def _derive_application_secrets(self) -> tuple[bytes, bytes]:
        if self._shared_secret is None:
            _raise_tls(AlertDescription.INTERNAL_ERROR, 'shared secret is not available')
        if self._early_secret is None:
            self._early_secret = self._key_schedule.make_early_secret(None)
        handshake_secret = self._key_schedule.handshake_secret(self._early_secret, self._shared_secret)
        self._master_secret = self._key_schedule.master_secret(handshake_secret)
        return self._key_schedule.application_traffic_secrets(self._master_secret, self._transcript)

    def _finalize_post_handshake_secrets(self) -> None:
        if self._master_secret is None:
            return
        self._exporter_master_secret = self._key_schedule.exporter_master_secret(self._master_secret, self._transcript)
        self._resumption_master_secret = self._key_schedule.resumption_master_secret(self._master_secret, self._transcript)
        if self._traffic_secrets is not None:
            self._traffic_secrets.exporter_master_secret = self._exporter_master_secret
            self._traffic_secrets.resumption_master_secret = self._resumption_master_secret

    def _load_selected_peer_certificate(self) -> x509.Certificate:
        if not self.peer_certificate_chain_pem:
            _raise_tls(AlertDescription.BAD_CERTIFICATE, 'peer certificate chain is missing')
        try:
            if self.validation_policy is None:
                policy = CertificateValidationPolicy(
                    purpose=CertificatePurpose.SERVER_AUTH if self.is_client else CertificatePurpose.CLIENT_AUTH,
                )
            else:
                policy = self.validation_policy
            leaf = verify_certificate_chain(
                self.peer_certificate_chain_pem,
                self.trusted_certificates,
                server_name=self.server_name if self.is_client else '',
                policy=policy,
            )
        except ProtocolError as exc:
            _raise_tls(AlertDescription.BAD_CERTIFICATE, str(exc))
        self.peer_certificate_pem = leaf.public_bytes(serialization.Encoding.PEM)
        return leaf

__all__ = [name for name in globals() if not name.startswith('__')]
