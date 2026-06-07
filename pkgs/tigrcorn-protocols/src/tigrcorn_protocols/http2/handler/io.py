from __future__ import annotations

from .imports import *


class HTTP2IOMixin:
    def _record_keepalive_activity(self) -> None:
        if self.keepalive is not None:
            self.keepalive.record_activity()


    async def _keepalive_loop(self) -> None:
        while self.running and not self.writer.is_closing():
            await asyncio.sleep(0.05)
            if self.keepalive is None or not self.running:
                return
            if not self.state.remote_settings_seen:
                continue
            if self.keepalive.ping_timed_out():
                self.running = False
                self.writer.close()
                with suppress(Exception):
                    await self.writer.wait_closed()
                return
            payload = self.keepalive.next_ping_payload()
            if payload is None:
                continue
            await self._write_raw(serialize_ping(payload, ack=False), record_activity=False)


    async def handle(self) -> None:
        await self._ensure_preface()
        try:
            await self._write_raw(serialize_settings(self.state.local_settings))
            if self._initial_connection_window_increment:
                await self._write_raw(serialize_window_update(0, self._initial_connection_window_increment))
            if self.keepalive is not None:
                self.keepalive_task = asyncio.create_task(self._keepalive_loop(), name='tigrcorn-h2-keepalive')
            while self.running:
                if self._should_finish_after_peer_goaway():
                    break
                frames = self.frame_buffer.pop_all()
                if frames:
                    for frame in frames:
                        await self._handle_frame(frame)
                    continue
                data = await asyncio.wait_for(self.reader.read(65535), timeout=self.config.http.read_timeout)
                if not data:
                    break
                self.frame_buffer.feed(data)
        finally:
            if self.keepalive_task is not None:
                self.keepalive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.keepalive_task
            await self._shutdown_streams()


    async def _ensure_preface(self) -> None:
        if self.prebuffer == H2_PREFACE:
            self.state.preface_seen = True
            return
        if self.prebuffer:
            raise ProtocolError("unexpected HTTP/2 prebuffer state")
        received = await self.reader.readexactly(len(H2_PREFACE))
        if received != H2_PREFACE:
            raise ProtocolError("invalid HTTP/2 client preface")
        self.state.preface_seen = True


    async def _write_raw(self, data: bytes, *, record_activity: bool = True) -> None:
        async with self.writer_lock:
            self.writer.write(data)
            await self.writer.drain()
        if record_activity:
            self._record_keepalive_activity()

