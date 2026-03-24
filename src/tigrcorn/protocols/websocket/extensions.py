from __future__ import annotations

from dataclasses import dataclass
import zlib

from tigrcorn.errors import ProtocolError
from tigrcorn.utils.headers import get_headers

_PERMESSAGE_DEFLATE = b"permessage-deflate"
_SERVER_NO_CONTEXT_TAKEOVER = b"server_no_context_takeover"
_CLIENT_NO_CONTEXT_TAKEOVER = b"client_no_context_takeover"
_SERVER_MAX_WINDOW_BITS = b"server_max_window_bits"
_CLIENT_MAX_WINDOW_BITS = b"client_max_window_bits"

_VALID_PMD_PARAMETERS = {
    _SERVER_NO_CONTEXT_TAKEOVER,
    _CLIENT_NO_CONTEXT_TAKEOVER,
    _SERVER_MAX_WINDOW_BITS,
    _CLIENT_MAX_WINDOW_BITS,
}


def _split_quoted(value: bytes, delimiter: int) -> list[bytes]:
    parts: list[bytes] = []
    buf = bytearray()
    in_quote = False
    escape = False
    for byte in value:
        if escape:
            buf.append(byte)
            escape = False
            continue
        if in_quote:
            if byte == 0x5C:  # backslash
                escape = True
                continue
            if byte == 0x22:
                in_quote = False
            buf.append(byte)
            continue
        if byte == 0x22:
            in_quote = True
            buf.append(byte)
            continue
        if byte == delimiter:
            part = bytes(buf).strip()
            if part:
                parts.append(part)
            buf.clear()
            continue
        buf.append(byte)
    if in_quote:
        raise ProtocolError('malformed websocket extension header')
    part = bytes(buf).strip()
    if part:
        parts.append(part)
    return parts


def _parse_token_value(value: bytes) -> bytes:
    raw = value.strip()
    if len(raw) >= 2 and raw[:1] == raw[-1:] == b'"':
        inner = raw[1:-1]
        if b'"' in inner:
            raise ProtocolError('malformed websocket extension parameter value')
        return inner
    return raw


def _parse_window_bits(value: bytes) -> int:
    if not value or (len(value) > 1 and value.startswith(b'0')):
        raise ProtocolError('invalid permessage-deflate window bits parameter')
    try:
        bits = int(value.decode('ascii', 'strict'))
    except UnicodeDecodeError as exc:
        raise ProtocolError('invalid permessage-deflate window bits parameter') from exc
    except ValueError as exc:
        raise ProtocolError('invalid permessage-deflate window bits parameter') from exc
    if not 8 <= bits <= 15:
        raise ProtocolError('invalid permessage-deflate window bits parameter')
    return bits


@dataclass(slots=True, frozen=True)
class PerMessageDeflateOffer:
    server_no_context_takeover: bool = False
    client_no_context_takeover: bool = False
    server_max_window_bits: int | None = None
    client_max_window_bits_requested: bool = False
    client_max_window_bits: int | None = None


@dataclass(slots=True, frozen=True)
class PerMessageDeflateAgreement:
    server_no_context_takeover: bool = False
    client_no_context_takeover: bool = False
    server_max_window_bits: int | None = None
    client_max_window_bits: int | None = None

    def as_header_value(self) -> bytes:
        params = [b'permessage-deflate']
        if self.server_no_context_takeover:
            params.append(_SERVER_NO_CONTEXT_TAKEOVER)
        if self.client_no_context_takeover:
            params.append(_CLIENT_NO_CONTEXT_TAKEOVER)
        if self.server_max_window_bits is not None:
            params.append(_SERVER_MAX_WINDOW_BITS + b'=' + str(self.server_max_window_bits).encode('ascii'))
        if self.client_max_window_bits is not None:
            params.append(_CLIENT_MAX_WINDOW_BITS + b'=' + str(self.client_max_window_bits).encode('ascii'))
        return b'; '.join(params)


class PerMessageDeflateRuntime:
    def __init__(self, agreement: PerMessageDeflateAgreement) -> None:
        self.agreement = agreement
        self._compressor: zlib.compressobj | None = None
        self._decompressor: zlib.decompressobj | None = None

    @staticmethod
    def _runtime_window_bits(bits: int | None) -> int:
        if bits is None:
            return 15
        # Python's raw DEFLATE bindings reject 8 here; fall back to the smallest
        # supported raw window while preserving interoperable decompression.
        return max(bits, 9)

    def _new_compressor(self) -> zlib.compressobj:
        return zlib.compressobj(wbits=-self._runtime_window_bits(self.agreement.server_max_window_bits))

    def _new_decompressor(self) -> zlib.decompressobj:
        return zlib.decompressobj(wbits=-self._runtime_window_bits(self.agreement.client_max_window_bits))

    def compress_message(self, payload: bytes) -> bytes:
        if self._compressor is None or self.agreement.server_no_context_takeover:
            self._compressor = self._new_compressor()
        compressed = self._compressor.compress(payload) + self._compressor.flush(zlib.Z_SYNC_FLUSH)
        if not compressed.endswith(b'\x00\x00\xff\xff'):
            raise RuntimeError('unexpected permessage-deflate trailer')
        if self.agreement.server_no_context_takeover:
            self._compressor = None
        return compressed[:-4]

    def decompress_message(self, payload: bytes) -> bytes:
        if self._decompressor is None or self.agreement.client_no_context_takeover:
            self._decompressor = self._new_decompressor()
        try:
            data = self._decompressor.decompress(payload + b'\x00\x00\xff\xff')
        except zlib.error as exc:
            raise ProtocolError('invalid permessage-deflate payload') from exc
        if self._decompressor.unconsumed_tail or self._decompressor.unused_data:
            raise ProtocolError('invalid permessage-deflate payload')
        if self.agreement.client_no_context_takeover:
            self._decompressor = None
        return data


def _iter_extension_elements(values: list[bytes]) -> list[tuple[bytes, list[tuple[bytes, bytes | None]]]]:
    joined = b', '.join(value.strip() for value in values if value.strip())
    if not joined:
        return []
    elements: list[tuple[bytes, list[tuple[bytes, bytes | None]]]] = []
    for item in _split_quoted(joined, 0x2C):  # comma
        parts = _split_quoted(item, 0x3B)  # semicolon
        if not parts:
            continue
        name = parts[0].strip().lower()
        params: list[tuple[bytes, bytes | None]] = []
        for raw_param in parts[1:]:
            if not raw_param:
                continue
            if b'=' in raw_param:
                raw_name, raw_value = raw_param.split(b'=', 1)
                param_name = raw_name.strip().lower()
                param_value = _parse_token_value(raw_value)
            else:
                param_name = raw_param.strip().lower()
                param_value = None
            if not param_name:
                raise ProtocolError('malformed websocket extension parameter')
            params.append((param_name, param_value))
        elements.append((name, params))
    return elements


def parse_permessage_deflate_offers(headers: list[tuple[bytes, bytes]]) -> list[PerMessageDeflateOffer]:
    offers: list[PerMessageDeflateOffer] = []
    for name, params in _iter_extension_elements(get_headers(headers, b'sec-websocket-extensions')):
        if name != _PERMESSAGE_DEFLATE:
            continue
        try:
            offers.append(_parse_offer_parameters(params))
        except ProtocolError:
            continue
    return offers




def default_permessage_deflate_agreement(offers: list[PerMessageDeflateOffer]) -> PerMessageDeflateAgreement | None:
    """Choose a default server agreement for a valid permessage-deflate offer set.

    The server accepts the first valid offer and mirrors explicit window constraints so
    the generated response header corresponds to the client offer across websocket
    carriers, including HTTP/2 and HTTP/3 third-party clients that require explicit
    parameter echoing.
    """
    if not offers:
        return None
    offer = offers[0]
    return PerMessageDeflateAgreement(
        server_no_context_takeover=offer.server_no_context_takeover,
        client_no_context_takeover=False,
        server_max_window_bits=offer.server_max_window_bits,
        client_max_window_bits=offer.client_max_window_bits if offer.client_max_window_bits_requested else None,
    )
def negotiate_permessage_deflate(
    *,
    request_headers: list[tuple[bytes, bytes]],
    response_headers: list[tuple[bytes, bytes]],
) -> PerMessageDeflateAgreement | None:
    response_values = get_headers(response_headers, b'sec-websocket-extensions')
    if not response_values:
        return None
    response_elements = _iter_extension_elements(response_values)
    if len(response_elements) != 1 or response_elements[0][0] != _PERMESSAGE_DEFLATE:
        raise RuntimeError('unsupported websocket extension negotiation')
    agreement = _parse_response_parameters(response_elements[0][1])
    offers = parse_permessage_deflate_offers(request_headers)
    if not offers:
        raise RuntimeError('websocket extension not offered by the client')
    for offer in offers:
        if _agreement_matches_offer(agreement, offer):
            return agreement
    raise RuntimeError('websocket extension negotiation does not correspond to a client offer')


def _parse_offer_parameters(params: list[tuple[bytes, bytes | None]]) -> PerMessageDeflateOffer:
    server_no_context_takeover = False
    client_no_context_takeover = False
    server_max_window_bits: int | None = None
    client_max_window_bits_requested = False
    client_max_window_bits: int | None = None
    seen: set[bytes] = set()
    for name, value in params:
        if name not in _VALID_PMD_PARAMETERS or name in seen:
            raise ProtocolError('invalid permessage-deflate offer')
        seen.add(name)
        if name == _SERVER_NO_CONTEXT_TAKEOVER:
            if value is not None:
                raise ProtocolError('invalid permessage-deflate offer')
            server_no_context_takeover = True
            continue
        if name == _CLIENT_NO_CONTEXT_TAKEOVER:
            if value is not None:
                raise ProtocolError('invalid permessage-deflate offer')
            client_no_context_takeover = True
            continue
        if name == _SERVER_MAX_WINDOW_BITS:
            if value is None:
                raise ProtocolError('invalid permessage-deflate offer')
            server_max_window_bits = _parse_window_bits(value)
            continue
        if name == _CLIENT_MAX_WINDOW_BITS:
            client_max_window_bits_requested = True
            if value is not None:
                client_max_window_bits = _parse_window_bits(value)
            continue
    return PerMessageDeflateOffer(
        server_no_context_takeover=server_no_context_takeover,
        client_no_context_takeover=client_no_context_takeover,
        server_max_window_bits=server_max_window_bits,
        client_max_window_bits_requested=client_max_window_bits_requested,
        client_max_window_bits=client_max_window_bits,
    )


def _parse_response_parameters(params: list[tuple[bytes, bytes | None]]) -> PerMessageDeflateAgreement:
    server_no_context_takeover = False
    client_no_context_takeover = False
    server_max_window_bits: int | None = None
    client_max_window_bits: int | None = None
    seen: set[bytes] = set()
    for name, value in params:
        if name not in _VALID_PMD_PARAMETERS or name in seen:
            raise RuntimeError('unsupported websocket extension negotiation')
        seen.add(name)
        if name == _SERVER_NO_CONTEXT_TAKEOVER:
            if value is not None:
                raise RuntimeError('unsupported websocket extension negotiation')
            server_no_context_takeover = True
            continue
        if name == _CLIENT_NO_CONTEXT_TAKEOVER:
            if value is not None:
                raise RuntimeError('unsupported websocket extension negotiation')
            client_no_context_takeover = True
            continue
        if name == _SERVER_MAX_WINDOW_BITS:
            if value is None:
                raise RuntimeError('unsupported websocket extension negotiation')
            server_max_window_bits = _parse_window_bits(value)
            continue
        if value is None:
            raise RuntimeError('unsupported websocket extension negotiation')
        client_max_window_bits = _parse_window_bits(value)
    return PerMessageDeflateAgreement(
        server_no_context_takeover=server_no_context_takeover,
        client_no_context_takeover=client_no_context_takeover,
        server_max_window_bits=server_max_window_bits,
        client_max_window_bits=client_max_window_bits,
    )


def _agreement_matches_offer(agreement: PerMessageDeflateAgreement, offer: PerMessageDeflateOffer) -> bool:
    if offer.server_no_context_takeover and not agreement.server_no_context_takeover:
        return False
    if offer.server_max_window_bits is not None:
        if agreement.server_max_window_bits is None or agreement.server_max_window_bits > offer.server_max_window_bits:
            return False
    if agreement.client_max_window_bits is not None:
        if not offer.client_max_window_bits_requested:
            return False
        if offer.client_max_window_bits is not None and agreement.client_max_window_bits > offer.client_max_window_bits:
            return False
    return True
