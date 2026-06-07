from __future__ import annotations

from .imports import *
from .models import *
from .ssl_object import *
from .records import *
from .certificates import *

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

__all__ = [name for name in globals() if not name.startswith('__')]
