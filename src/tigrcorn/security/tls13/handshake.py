from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa, x25519, padding as asym_padding
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from tigrcorn.errors import ProtocolError
from tigrcorn.security.x509.path import (
    CertificatePurpose,
    CertificateValidationPolicy,
    load_pem_certificates,
    verify_certificate_chain,
)
from tigrcorn.security.tls13.extensions import (
    CIPHER_TLS_AES_128_GCM_SHA256,
    CIPHER_TLS_AES_256_GCM_SHA384,
    GROUP_SECP256R1,
    GROUP_X25519,
    PSK_MODE_DHE_KE,
    QUIC_EARLY_DATA_SENTINEL,
    SIG_ECDSA_SECP256R1_SHA256,
    SIG_ED25519,
    SIG_RSA_PSS_PSS_SHA256,
    SIG_RSA_PSS_RSAE_SHA256,
    SUPPORTED_CERTIFICATE_SIGNATURE_SCHEMES,
    SUPPORTED_CIPHER_SUITES,
    SUPPORTED_GROUPS,
    SUPPORTED_SIGNATURE_SCHEMES,
    CipherSuiteParameters,
    ExtensionType,
    OfferedPsks,
    PskIdentity,
    TlsExtension,
    TransportParameters,
    cipher_suite_parameters,
    extension_dict,
    encode_pre_shared_key_client_without_binders,
)
from tigrcorn.security.tls13.key_schedule import Tls13KeySchedule
from tigrcorn.security.tls13.messages import (
    HELLO_RETRY_REQUEST_RANDOM,
    Certificate,
    CertificateEntry,
    CertificateRequest,
    CertificateVerify,
    ClientHello,
    EncryptedExtensions,
    Finished,
    HandshakeMessage,
    KeyUpdate,
    NeedMoreData,
    NewSessionTicket,
    ServerHello,
    decode_handshake_message,
)
from tigrcorn.security.tls13.transcript import HandshakeTranscript
from tigrcorn.transports.quic.tls_adapter import split_handshake_flights

_SERVER_CERT_VERIFY_CONTEXT = b'TLS 1.3, server CertificateVerify'
_CLIENT_CERT_VERIFY_CONTEXT = b'TLS 1.3, client CertificateVerify'
_QUIC_TLS_ALERT_BASE = 0x0100
_QUIC_TRANSPORT_ERROR_PROTOCOL_VIOLATION = 0x0A
_MAX_TICKET_LIFETIME_SECONDS = 7 * 24 * 60 * 60
_MAX_AGE_SKEW_MS = 10_000


class AlertDescription:
    UNEXPECTED_MESSAGE = 10
    HANDSHAKE_FAILURE = 40
    BAD_CERTIFICATE = 42
    UNSUPPORTED_CERTIFICATE = 43
    CERTIFICATE_EXPIRED = 45
    CERTIFICATE_UNKNOWN = 46
    ILLEGAL_PARAMETER = 47
    UNKNOWN_CA = 48
    DECODE_ERROR = 50
    DECRYPT_ERROR = 51
    PROTOCOL_VERSION = 70
    INTERNAL_ERROR = 80
    MISSING_EXTENSION = 109
    CERTIFICATE_REQUIRED = 116


class TlsAlertError(ProtocolError):
    def __init__(self, description: int, message: str) -> None:
        super().__init__(message)
        self.description = description
        self.quic_error_code = _QUIC_TLS_ALERT_BASE + description


class QuicTransportError(ProtocolError):
    def __init__(self, error_code: int, message: str) -> None:
        super().__init__(message)
        self.quic_error_code = error_code


@dataclass(slots=True)
class HandshakeFlight:
    packet_space: str
    data: bytes


@dataclass(slots=True)
class QuicTrafficSecrets:
    client_handshake_secret: bytes
    server_handshake_secret: bytes
    client_application_secret: bytes
    server_application_secret: bytes
    client_early_secret: bytes | None = None
    exporter_master_secret: bytes | None = None
    resumption_master_secret: bytes | None = None


@dataclass(slots=True)
class QuicSessionTicket:
    ticket: bytes
    resumption_secret: bytes
    server_name: str
    alpn: str
    transport_parameters: TransportParameters
    ticket_age_add: int
    ticket_nonce: bytes
    ticket_lifetime: int
    issued_at: int
    cipher_suite: int = CIPHER_TLS_AES_128_GCM_SHA256
    max_early_data_size: int = 0

    def serialize(self) -> bytes:
        payload = {
            'ticket': _b64(self.ticket),
            'resumption_secret': _b64(self.resumption_secret),
            'server_name': self.server_name,
            'alpn': self.alpn,
            'transport_parameters': _b64(self.transport_parameters.to_bytes()),
            'ticket_age_add': self.ticket_age_add,
            'ticket_nonce': _b64(self.ticket_nonce),
            'ticket_lifetime': self.ticket_lifetime,
            'issued_at': self.issued_at,
            'cipher_suite': self.cipher_suite,
            'max_early_data_size': self.max_early_data_size,
        }
        return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')

    @classmethod
    def deserialize(cls, data: bytes) -> 'QuicSessionTicket':
        payload = json.loads(data.decode('utf-8'))
        return cls(
            ticket=_unb64(payload['ticket']),
            resumption_secret=_unb64(payload['resumption_secret']),
            server_name=str(payload['server_name']),
            alpn=str(payload['alpn']),
            transport_parameters=TransportParameters.from_bytes(_unb64(payload['transport_parameters'])),
            ticket_age_add=int(payload['ticket_age_add']),
            ticket_nonce=_unb64(payload['ticket_nonce']),
            ticket_lifetime=int(payload['ticket_lifetime']),
            issued_at=int(_normalize_ticket_payload(payload)['issued_at']),
            cipher_suite=int(payload.get('cipher_suite', CIPHER_TLS_AES_128_GCM_SHA256)),
            max_early_data_size=int(payload.get('max_early_data_size', 0)),
        )


_REPLAY_CACHE: dict[bytes, int] = {}



def _purge_replay_cache(now_ms: int) -> None:
    expired = [key for key, expiry in _REPLAY_CACHE.items() if expiry <= now_ms]
    for key in expired:
        _REPLAY_CACHE.pop(key, None)



def _claim_ticket_for_0rtt(ticket_identity: bytes, *, now_ms: int, ticket_lifetime: int) -> bool:
    _purge_replay_cache(now_ms)
    token = hashlib.sha256(ticket_identity).digest()
    expiry = now_ms + (ticket_lifetime * 1000)
    if token in _REPLAY_CACHE:
        return False
    _REPLAY_CACHE[token] = expiry
    return True



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



def _signature_algorithms_for_public_key(public_key: object) -> tuple[int, ...]:
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        return (SIG_ED25519,)
    if isinstance(public_key, rsa.RSAPublicKey):
        return (SIG_RSA_PSS_RSAE_SHA256, SIG_RSA_PSS_PSS_SHA256)
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        return (SIG_ECDSA_SECP256R1_SHA256,)
    return ()



def _select_certificate_verify_scheme(offered: Sequence[int], public_key: object) -> int:
    compatible = _signature_algorithms_for_public_key(public_key)
    for scheme in offered:
        if scheme in compatible:
            return scheme
    _raise_tls(AlertDescription.HANDSHAKE_FAILURE, 'no compatible certificate signature algorithm')



def _sign_with_scheme(private_key: object, scheme: int, payload: bytes) -> bytes:
    if scheme == SIG_ED25519:
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'certificate key is not compatible with ed25519')
        return private_key.sign(payload)
    if scheme in {SIG_RSA_PSS_RSAE_SHA256, SIG_RSA_PSS_PSS_SHA256}:
        if not isinstance(private_key, rsa.RSAPrivateKey):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'certificate key is not compatible with RSA-PSS')
        return private_key.sign(
            payload,
            asym_padding.PSS(mgf=asym_padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
            hashes.SHA256(),
        )
    if scheme == SIG_ECDSA_SECP256R1_SHA256:
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'certificate key is not compatible with ECDSA')
        return private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'unsupported certificate verify signature algorithm')



def _verify_with_scheme(public_key: object, scheme: int, signature: bytes, payload: bytes) -> None:
    try:
        if scheme == SIG_ED25519:
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer certificate key is not compatible with ed25519')
            public_key.verify(signature, payload)
            return
        if scheme in {SIG_RSA_PSS_RSAE_SHA256, SIG_RSA_PSS_PSS_SHA256}:
            if not isinstance(public_key, rsa.RSAPublicKey):
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer certificate key is not compatible with RSA-PSS')
            public_key.verify(
                signature,
                payload,
                asym_padding.PSS(mgf=asym_padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
                hashes.SHA256(),
            )
            return
        if scheme == SIG_ECDSA_SECP256R1_SHA256:
            if not isinstance(public_key, ec.EllipticCurvePublicKey):
                _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer certificate key is not compatible with ECDSA')
            public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
            return
    except TlsAlertError:
        raise
    except Exception as exc:  # pragma: no cover - crypto backend specifics vary.
        _raise_tls(AlertDescription.DECRYPT_ERROR, 'peer CertificateVerify signature is invalid')
    _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'unsupported peer certificate verify signature algorithm')



def _generate_key_share(group: int) -> tuple[object, bytes]:
    if group == GROUP_X25519:
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        return private_key, public_key
    if group == GROUP_SECP256R1:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return private_key, public_key
    raise ValueError(f'unsupported TLS key share group: {group}')



def _derive_shared_secret(private_key: object, group: int, peer_key_exchange: bytes) -> bytes:
    try:
        if group == GROUP_X25519:
            if not isinstance(private_key, x25519.X25519PrivateKey):
                _raise_tls(AlertDescription.INTERNAL_ERROR, 'x25519 key share state is unavailable')
            peer_public = x25519.X25519PublicKey.from_public_bytes(peer_key_exchange)
            return private_key.exchange(peer_public)
        if group == GROUP_SECP256R1:
            if not isinstance(private_key, ec.EllipticCurvePrivateKey):
                _raise_tls(AlertDescription.INTERNAL_ERROR, 'secp256r1 key share state is unavailable')
            peer_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), peer_key_exchange)
            return private_key.exchange(ec.ECDH(), peer_public)
    except TlsAlertError:
        raise
    except Exception:  # pragma: no cover - crypto backend specifics vary.
        _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'peer key share could not be processed')
    _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'unsupported TLS key share group')



def _preferred_supported_group(*, supported_groups: Sequence[int], key_shares: dict[int, bytes]) -> int | None:
    for group in SUPPORTED_GROUPS:
        if group in key_shares:
            return group
    for group in SUPPORTED_GROUPS:
        if group in supported_groups:
            return group
    return None


def _select_cipher_suite(offered: Sequence[int], supported: Sequence[int]) -> int | None:
    for cipher_suite in supported:
        if cipher_suite in offered:
            return cipher_suite
    return None



def _ticket_protection_key(private_key_pem: bytes | None, certificate_pem: bytes | None) -> bytes:
    material = private_key_pem or certificate_pem or b'tigrcorn-quic-tls13-ticket-key'
    return hashlib.sha256(b'tigrcorn-ticket-v1' + material).digest()



def _seal_ticket(ticket_key: bytes, payload: dict[str, object]) -> bytes:
    serialized = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    mac = hmac.new(ticket_key, serialized, hashlib.sha256).digest()
    return b'TGT1' + mac + serialized



def _normalize_ticket_payload(payload: dict[str, object]) -> dict[str, object]:
    if 'version' in payload:
        return payload
    if 'v' in payload:
        return {
            'version': int(payload.get('v', 1)),
            'issued_at': int(payload['i']),
            'ticket_lifetime': int(payload['l']),
            'ticket_age_add': int(payload['a']),
            'ticket_nonce': str(payload['n']),
            'server_name': str(payload['s']),
            'alpn': str(payload['h']),
            'transport_parameters': str(payload['p']),
            'cipher_suite': int(payload.get('c', CIPHER_TLS_AES_128_GCM_SHA256)),
            'resumption_secret': str(payload['r']),
            'max_early_data_size': int(payload.get('e', 0)),
        }
    return payload



def _open_ticket(ticket_key: bytes, ticket: bytes) -> dict[str, object]:
    if not ticket.startswith(b'TGT1') or len(ticket) < 4 + 32:
        _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'invalid session ticket format')
    mac = ticket[4:36]
    serialized = ticket[36:]
    expected = hmac.new(ticket_key, serialized, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        _raise_tls(AlertDescription.ILLEGAL_PARAMETER, 'session ticket integrity verification failed')
    return _normalize_ticket_payload(json.loads(serialized.decode('utf-8')))



def _session_ticket_from_payload(payload: dict[str, object], *, opaque_ticket: bytes) -> QuicSessionTicket:
    payload = _normalize_ticket_payload(payload)
    return QuicSessionTicket(
        ticket=opaque_ticket,
        resumption_secret=_unb64(str(payload['resumption_secret'])),
        server_name=str(payload['server_name']),
        alpn=str(payload['alpn']),
        transport_parameters=TransportParameters.from_bytes(_unb64(str(payload['transport_parameters']))),
        ticket_age_add=int(payload['ticket_age_add']),
        ticket_nonce=_unb64(str(payload['ticket_nonce'])),
        ticket_lifetime=int(payload['ticket_lifetime']),
        issued_at=int(payload['issued_at']),
        cipher_suite=int(payload.get('cipher_suite', CIPHER_TLS_AES_128_GCM_SHA256)),
        max_early_data_size=int(payload.get('max_early_data_size', 0)),
    )




def _client_hello_without_binders(full_client_hello: bytes, binders: Sequence[bytes]) -> bytes:
    binders_length = 2 + sum(1 + len(binder) for binder in binders)
    if binders_length <= 2 or binders_length > len(full_client_hello):
        raise ProtocolError('invalid ClientHello pre_shared_key binder vector')
    return full_client_hello[:-binders_length]



def generate_self_signed_certificate(common_name: str = 'tigrcorn-quic', *, purpose: str = 'server') -> tuple[bytes, bytes]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    if purpose not in {'server', 'client', 'both'}:
        raise ValueError("purpose must be 'server', 'client', or 'both'")
    eku_oids: list[x509.ObjectIdentifier] = []
    if purpose in {'server', 'both'}:
        eku_oids.append(ExtendedKeyUsageOID.SERVER_AUTH)
    if purpose in {'client', 'both'}:
        eku_oids.append(ExtendedKeyUsageOID.CLIENT_AUTH)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(private_key.public_key()), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage(eku_oids), critical=False)
    )
    certificate = builder.sign(private_key, algorithm=None)
    return (
        certificate.public_bytes(serialization.Encoding.PEM),
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )


class QuicTlsHandshakeDriver:
    def __init__(
        self,
        *,
        is_client: bool,
        alpn: str | Sequence[str] = 'h3',
        server_name: str = 'localhost',
        transport_parameters: TransportParameters | None = None,
        certificate_pem: bytes | None = None,
        private_key_pem: bytes | None = None,
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
        self._private_key = serialization.load_pem_private_key(private_key_pem, password=None) if private_key_pem is not None else None
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

        initial_cipher_suite = self.session_ticket.cipher_suite if self.session_ticket is not None and self.session_ticket.cipher_suite in self.supported_cipher_suites else self.supported_cipher_suites[0]
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

    def _handle_client_hello(self, message: ClientHello, *, raw_message: bytes | None = None) -> bytes:
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
                self._client_early_secret = self._key_schedule.client_early_traffic_secret(early_secret, message.encode())
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
        self._last_client_hello_bytes = message.encode()
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
