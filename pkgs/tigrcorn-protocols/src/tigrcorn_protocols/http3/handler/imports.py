from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from tigrcorn_asgi.receive import HTTPRequestReceive, apply_request_trailer_policy
from tigrcorn_asgi.scopes.custom import build_custom_scope
from tigrcorn_asgi.scopes.http import build_http_scope
from tigrcorn_asgi.send import HTTPResponseCollector, iter_response_body_segments, response_body_segments_have_bytes
from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_core.errors import ProtocolError
from tigrcorn_observability.logging import AccessLogger
from tigrcorn_observability.metrics import Metrics
from tigrcorn_security.tls import build_server_ssl_context
from tigrcorn_protocols.connect import close_tcp_writer, half_close_tcp_writer, is_connect_allowed, parse_connect_authority
from tigrcorn_protocols.custom.adapters import adapt_scope
from tigrcorn_protocols.http1.parser import ParsedRequest
from tigrcorn_http.alt_svc import configured_alt_svc_values
from tigrcorn_http.entity import apply_response_entity_semantics, plan_file_backed_response_entity_semantics
from tigrcorn_protocols.http3.codec import (
    FRAME_DATA,
    FRAME_HEADERS,
    H3_CONNECT_ERROR,
    H3_ID_ERROR,
    H3_GENERAL_PROTOCOL_ERROR,
    H3_REQUEST_CANCELLED,
    SETTING_ENABLE_CONNECT_PROTOCOL,
    SETTING_H3_DATAGRAM,
    SETTING_MAX_FIELD_SECTION_SIZE,
    SETTING_QPACK_MAX_TABLE_CAPACITY,
    SETTING_WT_MAX_SESSIONS,
    SETTING_WT_ENABLED,
    HTTP3ConnectionError,
    HTTP3StreamError,
    encode_frame,
)
from tigrcorn_protocols.webtransport.wire import H3_FRAME_WEBTRANSPORT_STREAM, H3_STREAM_TYPE_WEBTRANSPORT
from tigrcorn_protocols.http3.streams import (
    STREAM_TYPE_QPACK_DECODER,
    STREAM_TYPE_QPACK_ENCODER,
    HTTP3ConnectionCore,
)
from tigrcorn_protocols.http3.websocket import H3WebSocketSession
from tigrcorn_protocols.sessions import RuntimeConnectionInventory, peer_id_from_address
from tigrcorn_protocols.webtransport.governance import WebTransportGovernanceError
from tigrcorn_protocols.webtransport.negotiation import negotiate_profiles, settings_for_profiles
from tigrcorn_protocols.webtransport.profiles import conflicting_request_profile, missing_peer_requirement, missing_request_requirement, profile_spec
from tigrcorn_transports.quic.connection import QuicConnection
from tigrcorn_transports.quic.handshake import QuicTlsHandshakeDriver, TransportParameters
from tigrcorn_transports.quic.packets import QuicLongHeaderPacket, QuicLongHeaderType, QuicRetryPacket, QuicShortHeaderPacket, QuicVersionNegotiationPacket, decode_packet
from tigrcorn_transports.udp.endpoint import UDPEndpoint
from tigrcorn_transports.udp.packet import UDPPacket
from tigrcorn_core.types import ASGIApp
from tigrcorn_core.utils.bytes import decode_quic_varint, encode_quic_varint
from tigrcorn_core.utils.authority import authority_allowed
from tigrcorn_core.utils.headers import apply_response_header_policy, sanitize_early_hints_headers, strip_connection_specific_headers

from .webtransport import _HTTP3WebTransportSession
from tigrcorn_protocols.scheduler.runtime import ProductionScheduler
from .session import HTTP3Session
