from __future__ import annotations


HTTP3_STREAM_PRESSURE_CERTIFICATION_SCOPES: tuple[str, ...] = ('stream-level-backpressure', 'connection-level-backpressure', 'goaway-pressure')
DEFAULT_HTTP3_REQUEST_PARSE_BUFFER_LIMIT = 65_536


def supported_http3_stream_pressure_certification_scopes() -> tuple[str, ...]:
    return HTTP3_STREAM_PRESSURE_CERTIFICATION_SCOPES

STREAM_TYPE_PUSH = 0x01
STREAM_TYPE_QPACK_ENCODER = 0x02
STREAM_TYPE_QPACK_DECODER = 0x03
SETTING_QPACK_MAX_TABLE_CAPACITY = 0x01
SETTING_MAX_FIELD_SECTION_SIZE = 0x06
SETTING_QPACK_BLOCKED_STREAMS = 0x07

