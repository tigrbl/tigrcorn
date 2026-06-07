from __future__ import annotations

from .imports import *
from .connect import HTTP2ConnectMixin
from .flow_control import HTTP2FlowControlMixin
from .frames import HTTP2FrameDispatchMixin
from .headers import HTTP2HeadersMixin
from .io import HTTP2IOMixin
from .requests import HTTP2RequestsMixin
from .responses import HTTP2ResponsesMixin
from .streams import HTTP2StreamsMixin
from .websocket_support import HTTP2WebSocketSupportMixin


class HTTP2ConnectionHandler(
    HTTP2IOMixin,
    HTTP2FrameDispatchMixin,
    HTTP2HeadersMixin,
    HTTP2FlowControlMixin,
    HTTP2StreamsMixin,
    HTTP2RequestsMixin,
    HTTP2ResponsesMixin,
    HTTP2ConnectMixin,
    HTTP2WebSocketSupportMixin,
):
    def __init__(
        self,
        *,
        app: ASGIApp,
        config: ServerConfig,
        access_logger: AccessLogger,
        scheduler: ProductionScheduler | None = None,
        metrics: Metrics | None = None,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client: tuple[str, int] | None,
        server: tuple[str, int] | tuple[str, None] | None,
        scheme: str,
        prebuffer: bytes = b"",
        scope_extensions: dict | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.access_logger = access_logger
        self.scheduler = scheduler
        self.metrics = metrics
        self.reader = reader
        self.writer = writer
        self.client = client
        self.server = server
        self.scheme = scheme
        self.prebuffer = prebuffer
        self.scope_extensions = dict(scope_extensions or {})
        self.state = H2ConnectionState()
        self.state.local_settings[SETTING_MAX_CONCURRENT_STREAMS] = self.config.http.http2_max_concurrent_streams
        self.state.local_settings[SETTING_MAX_HEADER_LIST_SIZE] = self.config.http.http2_max_headers_size
        self.state.local_settings[SETTING_MAX_FRAME_SIZE] = self.config.http.http2_max_frame_size
        self.state.local_settings[SETTING_INITIAL_WINDOW_SIZE] = self.config.http.http2_initial_stream_window_size
        self.state.connection_receive_window_target = self.config.http.http2_initial_connection_window_size
        self._initial_connection_window_increment = max(
            0,
            self.state.connection_receive_window_target - DEFAULT_SETTINGS[SETTING_INITIAL_WINDOW_SIZE],
        )
        if self._initial_connection_window_increment:
            self.state.connection_receive_window.increase(self._initial_connection_window_increment)
        self.streams = H2StreamRegistry()
        self.stream_tasks: dict[int, asyncio.Task[None]] = {}
        self.stream_work_leases: dict[int, WorkLease] = {}
        self.frame_buffer = FrameBuffer()
        self.frame_writer = FrameWriter(self.state.max_frame_size)
        self.writer_lock = asyncio.Lock()
        self.waiters: dict[int, FlowWaiter] = {}
        self.hpack_decoder = HPACKDecoder(
            max_table_size=DEFAULT_SETTINGS[0x1],
            max_header_list_size=self.state.max_header_list_size,
            max_header_block_size=self.config.http.http2_max_headers_size,
        )
        self.hpack_encoder = HPACKEncoder(max_table_size=DEFAULT_SETTINGS[0x1])
        self.keepalive_policy = KeepAlivePolicy(
            idle_timeout=self.config.http.idle_timeout,
            ping_interval=self.config.http.http2_keep_alive_interval,
            ping_timeout=self.config.http.http2_keep_alive_timeout,
        )
        self.keepalive = KeepAliveRuntime(self.keepalive_policy) if self.keepalive_policy.enabled else None
        self.keepalive_task: asyncio.Task[None] | None = None
        self.running = True
        self._continuation_stream_id: int | None = None

