import asyncio
import random
from contextlib import suppress
from typing import Any, Iterable

from tigrcorn_asgi.receive import HTTPRequestReceive, HTTPStreamingRequestReceive
from tigrcorn_asgi.scopes.http import build_http_scope
from tigrcorn_asgi.send import FileBodySegment, HTTPResponseCollector, iter_response_body_segments, response_body_segments_have_bytes
from tigrcorn_runtime.app_interfaces import resolve_app_dispatch
from tigrcorn_core.errors import ProtocolError
from tigrcorn_config.model import ListenerConfig, ServerConfig
from tigrcorn_core.constants import H2_PREFACE
from tigrcorn_transports.listeners.inproc import InProcListener
from tigrcorn_transports.listeners.pipe import PipeListener
from tigrcorn_transports.listeners.tcp import TCPListener
from tigrcorn_transports.listeners.udp import UDPListener
from tigrcorn_transports.listeners.unix import UnixListener
from tigrcorn_observability.logging import AccessLogger, configure_logging, resolve_logging_config
from tigrcorn_observability.metrics import StatsdExporter
from tigrcorn_observability.tracing import OtelExporter, span
from tigrcorn_protocols.connect import is_connect_allowed, parse_connect_authority
from tigrcorn_http.alt_svc import configured_alt_svc_values
from tigrcorn_http.entity import apply_response_entity_semantics, plan_file_backed_response_entity_semantics
from tigrcorn_protocols.http1.keepalive import apply_keep_alive_policy
from tigrcorn_protocols.http1.parser import ParsedRequestHead, read_http11_request_head
from tigrcorn_protocols.http1.serializer import finalize_chunked_body, serialize_http11_response_chunk, serialize_http11_response_head, serialize_http11_response_whole
from tigrcorn_protocols.http2.handler import HTTP2ConnectionHandler
from tigrcorn_protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn_protocols.lifespan.driver import LifespanManager
from tigrcorn_protocols.rawframed.handler import RawFramedApplicationHandler
from tigrcorn_protocols.websocket.handler import WebSocketConnectionHandler
from tigrcorn_protocols.scheduler import ProductionScheduler, SchedulerPolicy
from tigrcorn_protocols.sessions import RuntimeConnectionInventory, peer_id_from_address
from tigrcorn_security.tls import build_server_ssl_context, tls_extension_payload
from tigrcorn_runtime.server.hooks import run_async_hooks
from tigrcorn_runtime.server.state import ServerState
from tigrcorn_runtime.quic_cc import resolve_congestion_control
from tigrcorn_transports.tcp.reader import PrebufferedReader
from tigrcorn_transports.registry import (
    TRANSPORTS,
    TransportDomainAccounting,
    _normalize_listener_kind,
    transport_domain_diagnostics,
    validate_profile_transport_domains,
)
from tigrcorn_transports.quic.security import QuicOperationalSecurityRuntime
from tigrcorn_protocols.webtransport.governance import (
    WebTransportGovernanceManager,
    default_webtransport_budget_policy,
)
from tigrcorn_core.types import ASGIApp, StreamReaderLike
from tigrcorn_core.utils.authority import authority_allowed
from tigrcorn_core.utils.headers import get_header
from tigrcorn_core.utils.net import peer_parts
from tigrcorn_core.utils.proxy import resolve_proxy_view


__all__ = [name for name in globals() if not name.startswith('__')]
