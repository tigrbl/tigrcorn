from __future__ import annotations

from .imports import *
from .models import *
from .cipher_suites import *
from .vectors import *
from .common import *
from .key_share import *
from .psk import *
from .quic import *

def encode_extensions(extensions: Sequence[TlsExtension], *, message_context: str) -> bytes:
    payload = bytearray()
    for extension in extensions:
        raw = extension.raw_data
        if raw is None:
            raw = encode_extension_value(extension.extension_type, extension.value, message_context=message_context)
        payload.extend(int(extension.extension_type).to_bytes(2, 'big'))
        payload.extend(len(raw).to_bytes(2, 'big'))
        payload.extend(raw)
    return _u16_vector(bytes(payload))



def decode_extensions(data: bytes, *, message_context: str) -> tuple[TlsExtension, ...]:
    payload, offset = _read_u16_vector(data, 0)
    if offset != len(data):
        raise ProtocolError('invalid TLS extensions vector')
    inner = 0
    items: list[TlsExtension] = []
    while inner < len(payload):
        extension_type, inner = _read_u16(payload, inner)
        extension_data, inner = _read_u16_vector(payload, inner)
        value = decode_extension_value(extension_type, extension_data, message_context=message_context)
        items.append(TlsExtension(extension_type=extension_type, value=value, raw_data=extension_data))
    return tuple(items)



def encode_extension_value(extension_type: int, value: object, *, message_context: str) -> bytes:
    ext = ExtensionType(extension_type) if extension_type in set(item.value for item in ExtensionType) else None
    if ext == ExtensionType.SERVER_NAME:
        assert isinstance(value, str)
        return encode_server_name(value)
    if ext == ExtensionType.SUPPORTED_VERSIONS:
        if message_context == 'client_hello':
            return encode_supported_versions_client(tuple(int(item) for item in value))
        return encode_supported_versions_server(int(value))
    if ext == ExtensionType.SUPPORTED_GROUPS:
        return encode_supported_groups(tuple(int(item) for item in value))
    if ext in {ExtensionType.SIGNATURE_ALGORITHMS, ExtensionType.SIGNATURE_ALGORITHMS_CERT}:
        return encode_signature_algorithms(tuple(int(item) for item in value))
    if ext == ExtensionType.ALPN:
        if isinstance(value, str):
            return encode_alpn((value,))
        return encode_alpn(tuple(str(item) for item in value))
    if ext == ExtensionType.PSK_KEY_EXCHANGE_MODES:
        return encode_psk_key_exchange_modes(tuple(int(item) for item in value))
    if ext == ExtensionType.KEY_SHARE:
        if message_context == 'client_hello':
            return encode_keyshare_client(tuple((int(group), bytes(key_exchange)) for group, key_exchange in value))
        if message_context == 'hello_retry_request':
            return encode_keyshare_hrr(int(value))
        group, key_exchange = value
        return encode_keyshare_server(int(group), bytes(key_exchange))
    if ext == ExtensionType.COOKIE:
        return encode_cookie(bytes(value))
    if ext == ExtensionType.EARLY_DATA:
        size = QUIC_EARLY_DATA_SENTINEL if value is True else int(value)
        return encode_early_data(message_context, size)
    if ext == ExtensionType.PRE_SHARED_KEY:
        if message_context == 'client_hello':
            offered = value
            assert isinstance(offered, OfferedPsks)
            return encode_pre_shared_key_client(offered.identities, offered.binders)
        return encode_pre_shared_key_server(int(value))
    if ext == ExtensionType.QUIC_TRANSPORT_PARAMETERS:
        assert isinstance(value, TransportParameters)
        return encode_quic_transport_parameters(value)
    if isinstance(value, bytes):
        return value
    raise ProtocolError(f'unsupported TLS extension type {extension_type}')



def decode_extension_value(extension_type: int, data: bytes, *, message_context: str) -> object:
    try:
        ext = ExtensionType(extension_type)
    except ValueError:
        return data
    if ext == ExtensionType.SERVER_NAME:
        return decode_server_name(data)
    if ext == ExtensionType.SUPPORTED_VERSIONS:
        if message_context == 'client_hello':
            return decode_supported_versions_client(data)
        return decode_supported_versions_server(data)
    if ext == ExtensionType.SUPPORTED_GROUPS:
        return decode_supported_groups(data)
    if ext in {ExtensionType.SIGNATURE_ALGORITHMS, ExtensionType.SIGNATURE_ALGORITHMS_CERT}:
        return decode_signature_algorithms(data)
    if ext == ExtensionType.ALPN:
        protocols = decode_alpn(data)
        return protocols if message_context == 'client_hello' else protocols[0]
    if ext == ExtensionType.PSK_KEY_EXCHANGE_MODES:
        return decode_psk_key_exchange_modes(data)
    if ext == ExtensionType.KEY_SHARE:
        if message_context == 'client_hello':
            return decode_keyshare_client(data)
        if message_context == 'hello_retry_request':
            return decode_keyshare_hrr(data)
        return decode_keyshare_server(data)
    if ext == ExtensionType.COOKIE:
        return decode_cookie(data)
    if ext == ExtensionType.EARLY_DATA:
        return decode_early_data(data, message_context)
    if ext == ExtensionType.PRE_SHARED_KEY:
        if message_context == 'client_hello':
            return decode_pre_shared_key_client(data)
        return decode_pre_shared_key_server(data)
    if ext == ExtensionType.QUIC_TRANSPORT_PARAMETERS:
        return decode_quic_transport_parameters(data)
    return data



def extension_dict(extensions: Iterable[TlsExtension]) -> dict[int, object]:
    return {int(extension.extension_type): extension.value for extension in extensions}

__all__ = [name for name in globals() if not name.startswith('__')]
