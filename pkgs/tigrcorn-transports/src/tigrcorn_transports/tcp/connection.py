from __future__ import annotations

from dataclasses import dataclass
import asyncio


@dataclass(slots=True)
class TCPConnection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    @property
    def ssl_object(self):
        return self.writer.get_extra_info("ssl_object")
