from __future__ import annotations

from .imports import *
from .models import *
from .connection import *

async def wrap_server_tls_connection(
    raw_reader: asyncio.StreamReader,
    raw_writer: asyncio.StreamWriter,
    context: ServerTLSContext,
) -> PackageOwnedTLSConnection:
    connection = PackageOwnedTLSConnection(raw_reader, raw_writer, context)
    await connection.handshake()
    return connection

__all__ = [name for name in globals() if not name.startswith('__')]
