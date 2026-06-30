from __future__ import annotations

from .imports import *


class HTTP2InventoryMixin:
    def _inventory_session_id(self, stream_id: int) -> str | None:
        if self.connection_inventory is None or self.connection_id is None:
            return None
        return f"h2:{self.connection_id}:{stream_id}"

    def _open_inventory_session(
        self,
        stream_id: int,
        *,
        kind: str,
        metadata: dict | None = None,
    ) -> str | None:
        session_id = self._inventory_session_id(stream_id)
        if session_id is None:
            return None
        payload = {"protocol": "http2", "stream_id": stream_id}
        payload.update(metadata or {})
        self.connection_inventory.open_session(
            session_id,
            connection_id=self.connection_id,
            kind=kind,
            stream_ids=(str(stream_id),),
            metadata=payload,
        )
        self.connection_inventory.increment_connection_counter(self.connection_id, "streams")
        if kind == "http-request":
            self.connection_inventory.increment_connection_counter(self.connection_id, "requests")
        elif kind == "websocket":
            self.connection_inventory.increment_connection_counter(self.connection_id, "websockets")
        elif kind == "connect-tunnel":
            self.connection_inventory.increment_connection_counter(self.connection_id, "connect_tunnels")
        return session_id

    def _update_inventory_session(
        self,
        stream_id: int,
        *,
        state: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        session_id = self._inventory_session_id(stream_id)
        if session_id is None:
            return
        self.connection_inventory.update_session(session_id, state=state, metadata=metadata)

    def _close_inventory_session(self, stream_id: int, *, reason: str | None = None) -> None:
        session_id = self._inventory_session_id(stream_id)
        if session_id is None:
            return
        self.connection_inventory.close_session(session_id, reason=reason)
