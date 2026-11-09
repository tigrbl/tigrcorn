from __future__ import annotations

import argparse
import asyncio
import ssl


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()


async def _handle_client(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_host: str,
    upstream_port: int,
) -> None:
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(upstream_host, upstream_port)
    except OSError:
        client_writer.close()
        await client_writer.wait_closed()
        return
    tasks = [
        asyncio.create_task(_pipe(client_reader, upstream_writer)),
        asyncio.create_task(_pipe(upstream_reader, client_writer)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        upstream_writer.close()
        client_writer.close()
        await asyncio.gather(upstream_writer.wait_closed(), client_writer.wait_closed(), return_exceptions=True)


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=8443)
    parser.add_argument("--upstream-host", default="127.0.0.1")
    parser.add_argument("--upstream-port", type=int, default=8000)
    parser.add_argument("--certfile", required=True)
    parser.add_argument("--keyfile", required=True)
    args = parser.parse_args()

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(args.certfile, args.keyfile)
    server = await asyncio.start_server(
        lambda reader, writer: _handle_client(reader, writer, args.upstream_host, args.upstream_port),
        args.listen_host,
        args.listen_port,
        ssl=ssl_context,
    )
    async with server:
        await server.serve_forever()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
