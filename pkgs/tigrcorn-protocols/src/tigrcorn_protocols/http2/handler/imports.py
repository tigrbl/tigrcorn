from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import urlsplit

from tigrcorn_asgi.receive import HTTP2QueuedRequestReceive, HTTPRequestReceive, apply_request_trailer_policy
from tigrcorn_asgi.scopes.http import build_http_scope
from tigrcorn_asgi.send import HTTPResponseCollector, iter_response_body_segments, response_body_segments_have_bytes
from tigrcorn_config.model import ServerConfig
from tigrcorn_protocols.flow.keepalive import KeepAlivePolicy, KeepAliveRuntime
from tigrcorn_core.constants import H2_PREFACE
from tigrcorn_core.errors import ProtocolError
from tigrcorn_observability.metrics import Metrics
from tigrcorn_observability.logging import AccessLogger
from tigrcorn_http.alt_svc import configured_alt_svc_values
from tigrcorn_http.entity import apply_response_entity_semantics, plan_file_backed_response_entity_semantics
from tigrcorn_protocols.http1.parser import ParsedRequest
from tigrcorn_protocols.http2.codec import (
    DEFAULT_SETTINGS,
    H2_CONNECT_ERROR,
    FLAG_ACK,
    FLAG_END_HEADERS,
    FLAG_END_STREAM,
    FRAME_CONTINUATION,
    FRAME_DATA,
    FRAME_GOAWAY,
    FRAME_HEADERS,
    FRAME_PING,
    FRAME_PRIORITY,
    FRAME_PUSH_PROMISE,
    FRAME_RST_STREAM,
    FRAME_SETTINGS,
    FRAME_WINDOW_UPDATE,
    FrameBuffer,
    FrameWriter,
    HTTP2Frame,
    decode_settings,
    headers_payload_fragment,
    parse_goaway,
    parse_priority,
    parse_push_promise,
    parse_window_update,
    serialize_goaway,
    serialize_ping,
    serialize_push_promise,
    serialize_rst_stream,
    serialize_settings,
    serialize_settings_ack,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_ENABLE_PUSH,
    SETTING_INITIAL_WINDOW_SIZE,
    SETTING_MAX_CONCURRENT_STREAMS,
    SETTING_MAX_FRAME_SIZE,
    SETTING_MAX_HEADER_LIST_SIZE,
    serialize_window_update,
    strip_padding,
)
from tigrcorn_protocols.http2.flow import FlowWaiter, next_adaptive_window_target
from tigrcorn_protocols.http2.hpack import HPACKDecoder, HPACKEncoder
from tigrcorn_protocols.http2.state import H2ConnectionState, H2StreamLifecycle, H2StreamState
from tigrcorn_protocols.scheduler.runtime import ProductionScheduler, WorkLease
from tigrcorn_protocols.http2.streams import H2StreamRegistry
from tigrcorn_protocols.connect import close_tcp_writer, half_close_tcp_writer, is_connect_allowed, parse_connect_authority
from tigrcorn_protocols.http2.websocket import H2WebSocketSession
from tigrcorn_protocols.sessions import RuntimeConnectionInventory
from tigrcorn_core.types import ASGIApp
from tigrcorn_core.utils.authority import authority_allowed
from tigrcorn_core.utils.headers import apply_response_header_policy, sanitize_early_hints_headers, strip_connection_specific_headers

