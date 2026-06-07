from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from tigrcorn_protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn_protocols.http3.websocket import H3WebSocketSession
from tigrcorn_transports.quic.connection import QuicConnection

@dataclass(slots=True)
class HTTP3Session:
    addr: tuple[str, int]
    quic: QuicConnection
    runtime_id: str = ''
    h3: HTTP3ConnectionCore = field(default_factory=lambda: HTTP3ConnectionCore(role='server'))
    server_control_stream_sent: bool = False
    server_control_stream_id: int | None = None
    responded_streams: set[int] = field(default_factory=set)
    request_packets: int = 0
    server_qpack_encoder_stream_id: int | None = None
    server_qpack_decoder_stream_id: int | None = None
    bytes_received: int = 0
    bytes_sent: int = 0
    address_validated: bool = False
    session_ticket_issued: bool = False
    pending_outbound: list[bytes] = field(default_factory=list)
    timer_handle: asyncio.TimerHandle | None = None
    connect_tunnels: dict[int, _HTTP3ConnectTunnel] = field(default_factory=dict)
    websocket_sessions: dict[int, H3WebSocketSession] = field(default_factory=dict)
    webtransport_sessions: dict[int, _HTTP3WebTransportSession] = field(default_factory=dict)
    webtransport_streams: set[int] = field(default_factory=set)
    webtransport_stream_owners: dict[int, int] = field(default_factory=dict)
    webtransport_stream_prefaces: dict[int, bytearray] = field(default_factory=dict)
    stream_work_leases: dict[int, object] = field(default_factory=dict)
    early_data_accounted: bool = False
    peer_goaway_observed: bool = False
    last_quic_packets_lost_total: int = 0
    last_quic_pto_expirations_total: int = 0

