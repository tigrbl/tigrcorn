from __future__ import annotations

from .imports import *
from .connect import HTTP3ConnectMixin
from .custom import HTTP3CustomQuicMixin
from .lifecycle import HTTP3LifecycleMixin
from .outbound import HTTP3OutboundMixin
from .packet import HTTP3PacketMixin
from .priority_lock import PriorityLock
from .requests import HTTP3RequestsMixin
from .responses import HTTP3ResponsesMixin
from .websocket_runtime import HTTP3WebSocketRuntimeMixin
from .webtransport_datagrams import HTTP3WebTransportDatagramsMixin
from .webtransport_stream_flow import HTTP3WebTransportStreamFlowMixin
from .webtransport_streams import HTTP3WebTransportStreamsMixin
from .webtransport_support import HTTP3WebTransportSupportMixin


class HTTP3DatagramHandler(
    HTTP3PacketMixin,
    HTTP3WebTransportStreamFlowMixin,
    HTTP3WebTransportStreamsMixin,
    HTTP3WebTransportDatagramsMixin,
    HTTP3WebTransportSupportMixin,
    HTTP3WebSocketRuntimeMixin,
    HTTP3ConnectMixin,
    HTTP3RequestsMixin,
    HTTP3ResponsesMixin,
    HTTP3OutboundMixin,
    HTTP3CustomQuicMixin,
    HTTP3LifecycleMixin,
):
    _EARLY_DATA_TICKET_SIZE = 4096
    _WEBTRANSPORT_BIDI_STREAM_SIGNAL = H3_FRAME_WEBTRANSPORT_STREAM
    _WEBTRANSPORT_UNIDI_STREAM_SIGNAL = H3_STREAM_TYPE_WEBTRANSPORT

    def __init__(
        self,
        *,
        app: ASGIApp,
        config: ServerConfig,
        listener: ListenerConfig,
        access_logger: AccessLogger,
        scheduler: ProductionScheduler | None = None,
        metrics: Metrics | None = None,
        webtransport_governance: Any | None = None,
        connection_inventory: RuntimeConnectionInventory | None = None,
        congestion_controller_factory: Any | None = None,
        congestion_controller_options: Any | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.listener = listener
        self.access_logger = access_logger
        self.scheduler = scheduler
        self.metrics = metrics
        self.webtransport_governance = webtransport_governance
        self.connection_inventory = connection_inventory
        self.congestion_controller_factory = congestion_controller_factory
        self.congestion_controller_options = dict(congestion_controller_options or {})
        self.sessions: dict[tuple[str, int], HTTP3Session] = {}
        self.sessions_by_local_cid: dict[bytes, HTTP3Session] = {}
        self._session_sequence = 0
        self._lock = PriorityLock()
        self.webtransport_trace: list[dict[str, object]] = []


__all__ = ["HTTP3DatagramHandler", "HTTP3Session"]
