from __future__ import annotations

from dataclasses import dataclass
import asyncio


@dataclass(slots=True)
class UnixConnection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
