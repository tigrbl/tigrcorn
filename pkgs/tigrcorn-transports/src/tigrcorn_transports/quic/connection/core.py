from __future__ import annotations

from .imports import *
from .base import QuicConnectionBaseMixin
from .decode import QuicConnectionDecodeMixin
from .loss_api import QuicConnectionLossApiMixin
from .receive import QuicConnectionReceiveMixin
from .runtime import QuicConnectionRuntimeMixin
from .send import QuicConnectionSendMixin

class QuicConnection(
    QuicConnectionReceiveMixin,
    QuicConnectionDecodeMixin,
    QuicConnectionSendMixin,
    QuicConnectionRuntimeMixin,
    QuicConnectionLossApiMixin,
    QuicConnectionBaseMixin,
):
    def __init__(
        self,
        *,
        is_client: bool = False,
        version: int = 1,
        secret: bytes | None = None,
        local_cid: bytes | None = None,
        remote_cid: bytes | None = None,
        supported_versions: Sequence[int] | None = None,
        require_retry: bool = False,
        retry_token_lifetime_ms: int = 10_000,
        new_token_lifetime_ms: int = 7 * 24 * 60 * 60 * 1000,
        max_datagram_size: int = 1200,
    ) -> None:
        self.is_client = is_client
        self.version = version
        self.supported_versions = tuple(dict.fromkeys(tuple(supported_versions or (version,)) + (version,)))
        self.local_cid = generate_connection_id() if local_cid is None else local_cid
        self.remote_cid = generate_connection_id() if (is_client and remote_cid is None) else remote_cid
        self.secret = secret or derive_secret(self.local_cid, b'tigrcorn-quic')
        self.configured_max_datagram_size = max(int(max_datagram_size), _MIN_INITIAL_DATAGRAM_SIZE)
        self.peer_max_udp_payload_size: int | None = None
        # Backward-compatible alias for the currently effective QUIC UDP send ceiling.
        self.max_datagram_size = self.configured_max_datagram_size
        self.require_retry = require_retry
        self.retry_token_lifetime_ms = retry_token_lifetime_ms
        self.new_token_lifetime_ms = new_token_lifetime_ms
        self._packet_spaces: dict[str, _PacketSpaceState] = {
            PACKET_SPACE_INITIAL: _PacketSpaceState(name=PACKET_SPACE_INITIAL),
            PACKET_SPACE_HANDSHAKE: _PacketSpaceState(name=PACKET_SPACE_HANDSHAKE),
            PACKET_SPACE_APPLICATION: _PacketSpaceState(name=PACKET_SPACE_APPLICATION),
        }
        self.packet_numbers = _QuicPacketNumberSpaces()
        self._client_application_secret = derive_secret(self.secret, b'client 1rtt')
        self._server_application_secret = derive_secret(self.secret, b'server 1rtt')
        self.client_1rtt_keys = derive_quic_packet_protection_keys(self._client_application_secret)
        self.server_1rtt_keys = derive_quic_packet_protection_keys(self._server_application_secret)
        self._client_handshake_secret: bytes | None = None
        self._server_handshake_secret: bytes | None = None
        self.client_handshake_keys: QuicPacketProtectionKeys | None = None
        self.server_handshake_keys: QuicPacketProtectionKeys | None = None
        self.client_0rtt_keys: QuicPacketProtectionKeys | None = None
        self._handshake_traffic_installed = False
        self._application_traffic_installed = False
        self._send_key_phase = 0
        self._recv_key_phase = 0
        self.state = 'new'
        self.flow = QuicFlowControl(local_is_client=is_client)
        self.streams = QuicStreamManager(local_is_client=is_client)
        self.last_acked = -1
        self.congestion = _CongestionState()
        self._path_states: dict[Any, _PathRuntime] = {
            _DEFAULT_PATH_KEY: _PathRuntime(
                key=_DEFAULT_PATH_KEY,
                addr=None,
                recovery=QuicLossRecovery(max_datagram_size=self.max_datagram_size),
                max_udp_payload_size=self.configured_max_datagram_size,
            )
        }
        self._active_path_key: Any = _DEFAULT_PATH_KEY
        self.recovery = self._path_states[_DEFAULT_PATH_KEY].recovery
        self._timer_wheel = QuicTimerWheel()
        self._sent_packets: dict[tuple[str, int], _SentPacketMeta] = {}
        self._wire_datagram_packets: dict[bytes, list[tuple[str, int]]] = {}
        self._scheduled_specs: list[_ScheduledFrameSpec] = []
        self.path_challenges: set[bytes] = set()
        self.retire_connection_ids: list[int] = []
        self.handshake_driver: QuicTlsHandshakeDriver | None = None
        self._pending_handshake_datagrams: list[bytes] = []
        self._pending_auto_resets: list[tuple[int, int]] = []
        self.bytes_received = 0
        self.bytes_sent = 0
        self.address_validated = is_client
        self.connection_id_sequence = 0
        self.issued_connection_ids: dict[int, tuple[bytes, bytes]] = {}
        self.peer_connection_ids: dict[int, tuple[bytes, bytes]] = {}
        self.peer_transport_parameters: TransportParameters | None = None
        self.local_transport_parameters: TransportParameters | None = None
        self._peer_active_connection_id_limit = 4
        self._peer_default_stream_window = 65_535
        self._handshake_done_sent = False
        self._peer_new_tokens: list[bytes] = []
        self._token_secret = derive_secret(self.secret, b'quic-address-token', length=32)
        self._original_destination_connection_id: bytes | None = self.remote_cid if is_client else None
        self._peer_initial_source_connection_id: bytes | None = None
        self._first_server_source_connection_id: bytes | None = None
        self._retry_source_connection_id: bytes | None = None
        self._retry_token: bytes = b''
        self._received_retry = False
        self._sent_retry = False
        self._peer_preferred_address: bytes | None = None
        self._path_addr: tuple[str, int] | None = None
        self._ack_delay_exponent = 3
        self.packets_lost_total = 0
        self.pto_expirations_total = 0
        self._sync_packet_number_snapshot()

