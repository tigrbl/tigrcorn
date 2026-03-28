from __future__ import annotations

import asyncio
import contextlib
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from tigrcorn.config.model import ListenerConfig
from tigrcorn.errors import ProtocolError
from tigrcorn.security.tls13.handshake import QuicTlsHandshakeDriver, TlsAlertError
from tigrcorn.security.tls13.key_schedule import Tls13KeySchedule
from tigrcorn.security.tls13.messages import decode_handshake_message
from tigrcorn.security.policies import build_validation_policy_for_listener
from tigrcorn.security.x509.path import (
    CertificatePurpose,
    CertificateValidationPolicy,
    RevocationCache,
    RevocationCacheEntry,
    RevocationFetchPolicy,
    RevocationFreshnessPolicy,
    RevocationMaterial,
    RevocationMode,
    load_pem_certificates,
    verify_certificate_chain as _verify_certificate_chain,
    verify_certificate_hostname,
    verify_certificate_validity,
)
from tigrcorn.transports.quic.crypto import aes_gcm_decrypt, aes_gcm_encrypt

_TLS_CONTENT_CHANGE_CIPHER_SPEC = 20
_TLS_CONTENT_ALERT = 21
_TLS_CONTENT_HANDSHAKE = 22
_TLS_CONTENT_APPLICATION_DATA = 23
_TLS_LEGACY_RECORD_VERSION = 0x0303
_TLS_MAX_PLAINTEXT = 16384
_TLS_ALERT_LEVEL_FATAL = 2
_TLS_ALERT_CLOSE_NOTIFY = 0

_CIPHER_NAMES = {
    0x1301: ('TLS_AES_128_GCM_SHA256', 128),
    0x1302: ('TLS_AES_256_GCM_SHA384', 256),
}


@dataclass(frozen=True, slots=True)
class ServerTLSContext:
    certificate_pem: bytes
    private_key_pem: bytes
    private_key_password: bytes | None
    trusted_certificates: tuple[bytes, ...]
    alpn_protocols: tuple[str, ...]
    require_client_certificate: bool
    validation_policy: CertificateValidationPolicy
    cipher_suites: tuple[int, ...] = (0x1302, 0x1301)
    server_name: str = 'localhost'


@dataclass(slots=True)
class _RecordProtectionState:
    key: bytes
    iv: bytes
    sequence_number: int = 0

    def next_nonce(self) -> bytes:
        sequence = self.sequence_number.to_bytes(8, 'big')
        padded = b'\x00' * (len(self.iv) - len(sequence)) + sequence
        nonce = bytes(left ^ right for left, right in zip(self.iv, padded))
        self.sequence_number += 1
        return nonce


class PackageOwnedSSLObject:
    def __init__(
        self,
        *,
        selected_alpn_protocol: str | None,
        cipher_suite: int,
        peer_certificate: x509.Certificate | None,
    ) -> None:
        self._selected_alpn_protocol = selected_alpn_protocol
        self._cipher_suite = cipher_suite
        self._peer_certificate = peer_certificate
        self._peer_certificate_der = (
            peer_certificate.public_bytes(serialization.Encoding.DER)
            if peer_certificate is not None
            else None
        )

    def selected_alpn_protocol(self) -> str | None:
        return self._selected_alpn_protocol

    def version(self) -> str:
        return 'TLSv1.3'

    def cipher(self) -> tuple[str, str, int]:
        name, bits = _CIPHER_NAMES.get(self._cipher_suite, ('TLS_UNKNOWN', 0))
        return name, 'TLSv1.3', bits

    def getpeercert(self, binary_form: bool = False) -> dict[str, Any] | bytes | None:
        if self._peer_certificate is None:
            return None
        if binary_form:
            return self._peer_certificate_der
        return describe_peer_certificate(self._peer_certificate)


class PackageOwnedTLSConnection:
    def __init__(
        self,
        raw_reader: asyncio.StreamReader,
        raw_writer: asyncio.StreamWriter,
        context: ServerTLSContext,
    ) -> None:
        self._raw_reader = raw_reader
        self._raw_writer = raw_writer
        self._context = context
        self._driver = QuicTlsHandshakeDriver(
            is_client=False,
            alpn=context.alpn_protocols,
            server_name=context.server_name,
            certificate_pem=context.certificate_pem,
            private_key_pem=context.private_key_pem,
            private_key_password=context.private_key_password,
            trusted_certificates=context.trusted_certificates,
            require_client_certificate=context.require_client_certificate,
            transport_mode='stream',
            validation_policy=context.validation_policy,
            cipher_suites=context.cipher_suites,
        )
        self._read_lock = asyncio.Lock()
        self._write_lock = threading.Lock()
        self._closed = False
        self._eof = False
        self._plaintext_buffer = bytearray()
        self._handshake_inbound: _RecordProtectionState | None = None
        self._handshake_outbound: _RecordProtectionState | None = None
        self._application_inbound: _RecordProtectionState | None = None
        self._application_outbound: _RecordProtectionState | None = None
        self._ssl_object: PackageOwnedSSLObject | None = None

    @property
    def ssl_object(self) -> PackageOwnedSSLObject | None:
        return self._ssl_object

    async def handshake(self) -> None:
        try:
            server_flight = b''
            while not server_flight:
                content_type, payload = await self._read_raw_record()
                if content_type == _TLS_CONTENT_CHANGE_CIPHER_SPEC:
                    continue
                if content_type == _TLS_CONTENT_HANDSHAKE:
                    server_flight = self._driver.receive(payload)
                    continue
                if content_type == _TLS_CONTENT_ALERT:
                    self._eof = True
                    raise ProtocolError('peer closed the TLS handshake before completion')
                raise ProtocolError('unexpected TLS record before ServerHello')

            await self._send_server_flight(server_flight)

            while not self._driver.complete:
                content_type, payload = await self._read_raw_record()
                if content_type == _TLS_CONTENT_CHANGE_CIPHER_SPEC:
                    continue
                if content_type == _TLS_CONTENT_HANDSHAKE:
                    self._driver.receive(payload)
                    continue
                if content_type == _TLS_CONTENT_ALERT:
                    self._eof = True
                    raise ProtocolError('peer closed the TLS handshake before completion')
                if content_type != _TLS_CONTENT_APPLICATION_DATA:
                    raise ProtocolError('unexpected TLS record during encrypted handshake')
                if self._handshake_inbound is None:
                    raise ProtocolError('TLS handshake keys are unavailable')
                plaintext, inner_type = _decrypt_record(payload, self._handshake_inbound)
                if inner_type == _TLS_CONTENT_CHANGE_CIPHER_SPEC:
                    continue
                if inner_type == _TLS_CONTENT_HANDSHAKE:
                    self._driver.receive(plaintext)
                    continue
                if inner_type == _TLS_CONTENT_ALERT:
                    self._eof = True
                    raise ProtocolError('peer sent a fatal TLS alert during the handshake')
                raise ProtocolError('unexpected TLS inner content type during handshake')

            traffic = self._driver.traffic_secrets
            if traffic is None:
                raise ProtocolError('TLS handshake completed without negotiated traffic secrets')
            parameters = self._driver.cipher_parameters
            self._application_inbound = _build_record_state(
                traffic.client_application_secret,
                key_length=parameters.key_length,
                iv_length=parameters.iv_length,
                hash_name=parameters.hash_name,
            )
            self._application_outbound = _build_record_state(
                traffic.server_application_secret,
                key_length=parameters.key_length,
                iv_length=parameters.iv_length,
                hash_name=parameters.hash_name,
            )
            peer_certificate = None
            if self._driver.peer_certificate_pem is not None:
                peer_certificate = load_pem_certificates((self._driver.peer_certificate_pem,))[0]
            self._ssl_object = PackageOwnedSSLObject(
                selected_alpn_protocol=self._driver.selected_alpn,
                cipher_suite=getattr(self._driver, '_selected_cipher_suite'),
                peer_certificate=peer_certificate,
            )
        except TlsAlertError as exc:
            with contextlib.suppress(Exception):
                await self._send_plain_alert(int(exc.description))
            raise ProtocolError(str(exc)) from exc

    async def read(self, n: int = -1) -> bytes:
        if n == 0:
            return b''
        async with self._read_lock:
            if n < 0:
                while not self._eof:
                    await self._fill_plaintext_buffer()
                data = bytes(self._plaintext_buffer)
                self._plaintext_buffer.clear()
                return data
            while not self._plaintext_buffer and not self._eof:
                await self._fill_plaintext_buffer()
            if not self._plaintext_buffer and self._eof:
                return b''
            take = min(n, len(self._plaintext_buffer))
            data = bytes(self._plaintext_buffer[:take])
            del self._plaintext_buffer[:take]
            return data

    async def readexactly(self, n: int) -> bytes:
        if n < 0:
            raise ValueError('readexactly size must be non-negative')
        async with self._read_lock:
            while len(self._plaintext_buffer) < n and not self._eof:
                await self._fill_plaintext_buffer()
            if len(self._plaintext_buffer) < n:
                partial = bytes(self._plaintext_buffer)
                self._plaintext_buffer.clear()
                raise asyncio.IncompleteReadError(partial=partial, expected=n)
            data = bytes(self._plaintext_buffer[:n])
            del self._plaintext_buffer[:n]
            return data

    async def readuntil(self, separator: bytes = b'\n') -> bytes:
        return await self.readuntil_limited(separator, limit=None)

    async def readuntil_limited(self, separator: bytes = b'\n', *, limit: int | None) -> bytes:
        if not separator:
            raise ValueError('separator must not be empty')
        async with self._read_lock:
            while True:
                index = self._plaintext_buffer.find(separator)
                if index >= 0:
                    end = index + len(separator)
                    data = bytes(self._plaintext_buffer[:end])
                    del self._plaintext_buffer[:end]
                    return data
                if limit is not None and len(self._plaintext_buffer) > limit:
                    raise asyncio.LimitOverrunError('separator is not found, and chunk exceed the limit', consumed=len(self._plaintext_buffer))
                if self._eof:
                    partial = bytes(self._plaintext_buffer)
                    self._plaintext_buffer.clear()
                    raise asyncio.IncompleteReadError(partial=partial, expected=len(partial) + len(separator))
                await self._fill_plaintext_buffer()
                if limit is not None and len(self._plaintext_buffer) > limit:
                    raise asyncio.LimitOverrunError('separator is not found, and chunk exceed the limit', consumed=len(self._plaintext_buffer))

    def write(self, data: bytes) -> None:
        if self._closed or not data:
            return
        if self._application_outbound is None:
            raise RuntimeError('TLS application keys are not available')
        with self._write_lock:
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset + _TLS_MAX_PLAINTEXT]
                offset += len(chunk)
                record = _encrypt_record(chunk, _TLS_CONTENT_APPLICATION_DATA, self._application_outbound)
                self._raw_writer.write(record)

    async def drain(self) -> None:
        await self._raw_writer.drain()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._application_outbound is not None and not self._raw_writer.is_closing():
            with contextlib.suppress(Exception):
                self._raw_writer.write(
                    _encrypt_record(
                        bytes([1, _TLS_ALERT_CLOSE_NOTIFY]),
                        _TLS_CONTENT_ALERT,
                        self._application_outbound,
                    )
                )
        self._raw_writer.close()

    async def wait_closed(self) -> None:
        await self._raw_writer.wait_closed()

    def is_closing(self) -> bool:
        return self._closed or self._raw_writer.is_closing()

    def can_write_eof(self) -> bool:
        return False

    def write_eof(self) -> None:
        self.close()

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        if name == 'ssl_object':
            return self._ssl_object
        if name == 'sslcontext':
            return self._context
        if name == 'peercert' and self._ssl_object is not None:
            return self._ssl_object.getpeercert(binary_form=False)
        if name == 'cipher' and self._ssl_object is not None:
            return self._ssl_object.cipher()
        if name == 'tls.negotiated_alpn':
            return None if self._ssl_object is None else self._ssl_object.selected_alpn_protocol()
        return self._raw_writer.get_extra_info(name, default)

    async def _fill_plaintext_buffer(self) -> None:
        content_type, payload = await self._read_raw_record()
        if content_type == _TLS_CONTENT_CHANGE_CIPHER_SPEC:
            return
        if content_type == _TLS_CONTENT_ALERT:
            self._eof = True
            return
        if content_type != _TLS_CONTENT_APPLICATION_DATA:
            raise ProtocolError('unexpected TLS record after the handshake completed')
        if self._application_inbound is None:
            raise ProtocolError('TLS application keys are not available')
        plaintext, inner_type = _decrypt_record(payload, self._application_inbound)
        if inner_type == _TLS_CONTENT_APPLICATION_DATA:
            if plaintext:
                self._plaintext_buffer.extend(plaintext)
            return
        if inner_type == _TLS_CONTENT_ALERT:
            self._eof = True
            return
        if inner_type == _TLS_CONTENT_CHANGE_CIPHER_SPEC:
            return
        raise ProtocolError('unexpected TLS inner content type after the handshake completed')

    async def _send_server_flight(self, flight: bytes) -> None:
        _message, offset = decode_handshake_message(flight, 0)
        server_hello = flight[:offset]
        encrypted_handshake = flight[offset:]
        self._raw_writer.write(_encode_plain_record(_TLS_CONTENT_HANDSHAKE, server_hello))
        self._raw_writer.write(_encode_plain_record(_TLS_CONTENT_CHANGE_CIPHER_SPEC, b'\x01'))
        traffic = self._driver.traffic_secrets
        if traffic is None:
            raise ProtocolError('TLS handshake traffic secrets were not negotiated')
        parameters = self._driver.cipher_parameters
        self._handshake_inbound = _build_record_state(
            traffic.client_handshake_secret,
            key_length=parameters.key_length,
            iv_length=parameters.iv_length,
            hash_name=parameters.hash_name,
        )
        self._handshake_outbound = _build_record_state(
            traffic.server_handshake_secret,
            key_length=parameters.key_length,
            iv_length=parameters.iv_length,
            hash_name=parameters.hash_name,
        )
        if encrypted_handshake:
            self._raw_writer.write(_encrypt_record(encrypted_handshake, _TLS_CONTENT_HANDSHAKE, self._handshake_outbound))
        await self._raw_writer.drain()

    async def _read_raw_record(self) -> tuple[int, bytes]:
        try:
            header = await self._raw_reader.readexactly(5)
        except asyncio.IncompleteReadError:
            self._eof = True
            return _TLS_CONTENT_ALERT, b''
        content_type = header[0]
        length = int.from_bytes(header[3:5], 'big')
        try:
            payload = await self._raw_reader.readexactly(length)
        except asyncio.IncompleteReadError as exc:
            raise ProtocolError('truncated TLS record') from exc
        return content_type, payload

    async def _send_plain_alert(self, description: int) -> None:
        self._raw_writer.write(
            _encode_plain_record(_TLS_CONTENT_ALERT, bytes([_TLS_ALERT_LEVEL_FATAL, description]))
        )
        await self._raw_writer.drain()


def _build_record_state(secret: bytes, *, key_length: int, iv_length: int, hash_name: str) -> _RecordProtectionState:
    schedule = Tls13KeySchedule(hash_name=hash_name)
    return _RecordProtectionState(
        key=schedule.expand_label(secret, 'key', b'', key_length),
        iv=schedule.expand_label(secret, 'iv', b'', iv_length),
    )


def _encode_plain_record(content_type: int, payload: bytes) -> bytes:
    return bytes([content_type]) + _TLS_LEGACY_RECORD_VERSION.to_bytes(2, 'big') + len(payload).to_bytes(2, 'big') + payload


def _encrypt_record(payload: bytes, inner_content_type: int, state: _RecordProtectionState) -> bytes:
    inner = payload + bytes([inner_content_type])
    nonce = state.next_nonce()
    body_length = len(inner) + 16
    header = (
        bytes([_TLS_CONTENT_APPLICATION_DATA])
        + _TLS_LEGACY_RECORD_VERSION.to_bytes(2, 'big')
        + body_length.to_bytes(2, 'big')
    )
    ciphertext, tag = aes_gcm_encrypt(state.key, nonce, inner, aad=header)
    return header + ciphertext + tag


def _decrypt_record(payload: bytes, state: _RecordProtectionState) -> tuple[bytes, int]:
    if len(payload) < 16:
        raise ProtocolError('truncated TLS application-data record')
    header = (
        bytes([_TLS_CONTENT_APPLICATION_DATA])
        + _TLS_LEGACY_RECORD_VERSION.to_bytes(2, 'big')
        + len(payload).to_bytes(2, 'big')
    )
    ciphertext = payload[:-16]
    tag = payload[-16:]
    nonce = state.next_nonce()
    plaintext = aes_gcm_decrypt(state.key, nonce, ciphertext, tag, aad=header)
    index = len(plaintext) - 1
    while index >= 0 and plaintext[index] == 0:
        index -= 1
    if index < 0:
        raise ProtocolError('TLS inner plaintext is missing a content type')
    return plaintext[:index], plaintext[index]


def describe_peer_certificate(certificate: x509.Certificate) -> dict[str, Any]:
    return {
        'subject': certificate.subject.rfc4514_string(),
        'issuer': certificate.issuer.rfc4514_string(),
        'serial_number': hex(certificate.serial_number),
        'not_valid_before': _iso_utc(
            certificate.not_valid_before_utc if hasattr(certificate, 'not_valid_before_utc') else certificate.not_valid_before
        ),
        'not_valid_after': _iso_utc(
            certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else certificate.not_valid_after
        ),
    }


def tls_extension_payload(writer: Any) -> dict[str, Any] | None:
    ssl_object = getattr(writer, 'get_extra_info', lambda *args, **kwargs: None)('ssl_object')
    if ssl_object is None:
        return None
    payload: dict[str, Any] = {}
    selected_alpn = getattr(ssl_object, 'selected_alpn_protocol', lambda: None)()
    if selected_alpn is not None:
        payload['selected_alpn_protocol'] = selected_alpn
    getpeercert = getattr(ssl_object, 'getpeercert', None)
    if callable(getpeercert):
        peer_cert = getpeercert(binary_form=False)
        if peer_cert is not None:
            payload['peer_cert'] = peer_cert
    return payload or None


def build_server_ssl_context(listener: ListenerConfig) -> ServerTLSContext | None:
    if not listener.ssl_enabled:
        return None
    assert listener.ssl_certfile is not None
    assert listener.ssl_keyfile is not None
    certificate_pem = Path(listener.ssl_certfile).read_bytes()
    private_key_pem = Path(listener.ssl_keyfile).read_bytes()
    private_key_password = getattr(listener, 'ssl_keyfile_password', None)
    if private_key_password is not None and not isinstance(private_key_password, bytes):
        private_key_password = str(private_key_password).encode('utf-8')
    trusted = (Path(listener.ssl_ca_certs).read_bytes(),) if listener.ssl_ca_certs else ()
    validation_policy = build_validation_policy_for_listener(listener)
    server_name = _listener_server_name(listener)
    return ServerTLSContext(
        certificate_pem=certificate_pem,
        private_key_pem=private_key_pem,
        private_key_password=private_key_password,
        trusted_certificates=trusted,
        alpn_protocols=tuple(listener.alpn_protocols),
        require_client_certificate=listener.ssl_require_client_cert,
        validation_policy=validation_policy,
        cipher_suites=tuple(int(item) for item in (getattr(listener, 'resolved_cipher_suites', ()) or (0x1302, 0x1301))),
        server_name=server_name,
    )


async def wrap_server_tls_connection(
    raw_reader: asyncio.StreamReader,
    raw_writer: asyncio.StreamWriter,
    context: ServerTLSContext,
) -> PackageOwnedTLSConnection:
    connection = PackageOwnedTLSConnection(raw_reader, raw_writer, context)
    await connection.handshake()
    return connection


build_server_tls_context = build_server_ssl_context


def verify_certificate_chain(
    chain_pems: Iterable[bytes],
    trust_roots_pems: Iterable[bytes],
    *,
    server_name: str = '',
    moment: datetime | None = None,
    policy: CertificateValidationPolicy | None = None,
) -> x509.Certificate:
    return _verify_certificate_chain(
        chain_pems,
        trust_roots_pems,
        server_name=server_name,
        moment=moment,
        policy=policy,
    )


def _listener_server_name(listener: ListenerConfig) -> str:
    host = listener.host or 'localhost'
    if host in {'0.0.0.0', '::', ''}:
        return 'localhost'
    return host


def _iso_utc(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


__all__ = [
    'PackageOwnedSSLObject',
    'PackageOwnedTLSConnection',
    'ServerTLSContext',
    'build_server_ssl_context',
    'build_server_tls_context',
    'wrap_server_tls_connection',
    'tls_extension_payload',
    'CertificatePurpose',
    'CertificateValidationPolicy',
    'RevocationCache',
    'RevocationCacheEntry',
    'RevocationFetchPolicy',
    'RevocationFreshnessPolicy',
    'RevocationMaterial',
    'RevocationMode',
    'load_pem_certificates',
    'verify_certificate_validity',
    'verify_certificate_hostname',
    'verify_certificate_chain',
]
