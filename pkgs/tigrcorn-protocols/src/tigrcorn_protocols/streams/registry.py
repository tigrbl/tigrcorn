from __future__ import annotations

from dataclasses import dataclass, field

from .base import LogicalStream


@dataclass(slots=True)
class StreamRegistry:
    streams: dict[int, LogicalStream] = field(default_factory=dict)

    def add(self, stream: LogicalStream) -> LogicalStream:
        self.streams[stream.stream_id] = stream
        return stream

    def get(self, stream_id: int) -> LogicalStream | None:
        return self.streams.get(stream_id)

    def close(self, stream_id: int) -> None:
        stream = self.streams.pop(stream_id, None)
        if stream is not None:
            stream.close()
