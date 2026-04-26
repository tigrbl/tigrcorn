from __future__ import annotations

from tigrcorn_core.errors import ProtocolError
from tigrcorn_protocols.rawframed.frames import RawFrame, encode_frame, try_decode_frame
from tigrcorn_core.types import StreamReaderLike


async def read_frame(reader: StreamReaderLike, *, max_frame_size: int = 16 * 1024 * 1024) -> RawFrame:
    import struct

    prefix = await reader.readexactly(4)
    size = struct.unpack("!I", prefix)[0]
    if size > max_frame_size:
        raise ProtocolError("raw frame exceeds configured max_frame_size")
    return RawFrame(await reader.readexactly(size))


__all__ = ["RawFrame", "encode_frame", "read_frame", "try_decode_frame"]
