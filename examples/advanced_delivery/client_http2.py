from __future__ import annotations

import socket

from tigrcorn.constants import H2_PREFACE
from tigrcorn.protocols.http2.codec import FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS, FrameBuffer, FrameWriter, decode_settings, serialize_settings
from tigrcorn.protocols.http2.hpack import decode_header_block, encode_header_block


def _read_response(sock: socket.socket) -> tuple[list[list[tuple[bytes, bytes]]], bytes]:
    buf = FrameBuffer()
    header_blocks: list[list[tuple[bytes, bytes]]] = []
    body = bytearray()
    ended = False
    while not ended:
        data = sock.recv(65535)
        if not data:
            break
        buf.feed(data)
        for frame in buf.pop_all():
            if frame.frame_type == FRAME_SETTINGS and frame.payload:
                decode_settings(frame.payload)
            elif frame.frame_type == FRAME_HEADERS:
                header_blocks.append(decode_header_block(frame.payload))
                if frame.flags & 0x1:
                    ended = True
            elif frame.frame_type == FRAME_DATA:
                body.extend(frame.payload)
                if frame.flags & 0x1:
                    ended = True
    return header_blocks, bytes(body)


def main(host: str = '127.0.0.1', port: int = 8000) -> None:
    with socket.create_connection((host, port)) as sock:
        writer = FrameWriter()
        sock.sendall(H2_PREFACE)
        sock.sendall(serialize_settings({}))
        header_block = encode_header_block(
            [
                (b':method', b'GET'),
                (b':scheme', b'http'),
                (b':path', b'/early-hints'),
                (b':authority', b'localhost'),
            ]
        )
        sock.sendall(writer.headers(1, header_block, end_stream=True))
        header_blocks, body = _read_response(sock)
        for index, block in enumerate(header_blocks, start=1):
            print(f'HEADERS block {index}: {block}')
        print(body.decode('utf-8'))


if __name__ == '__main__':  # pragma: no cover
    main()
