from __future__ import annotations

import asyncio
import inspect
import os
import stat
from collections.abc import Awaitable, Callable
from pathlib import Path

from tigrcorn_core.errors import ServerError
from tigrcorn_transports.pipe.connection import PipeConnection

from .base import BaseListener


class PipeListener(BaseListener):
    def __init__(self, path: str) -> None:
        self.path = path
        self._callback: Callable[..., Awaitable[None] | None] | None = None
        self._reader_fd: int | None = None
        self._writer_fd: int | None = None
        self._connection: PipeConnection | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self, client_connected_cb):
        if not hasattr(os, 'mkfifo'):
            raise ServerError('named pipes are not available on this platform')
        self._callback = client_connected_cb
        self._loop = asyncio.get_running_loop()
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            mode = path.stat().st_mode
            if not stat.S_ISFIFO(mode):
                raise ServerError(f'{self.path!r} exists and is not a FIFO')
        else:
            os.mkfifo(path)
        self._reader_fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self._writer_fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        self._connection = PipeConnection(path=self.path, read_fd=self._reader_fd, write_fd=self._writer_fd)
        self._loop.add_reader(self._reader_fd, self._on_readable)

    def _on_readable(self) -> None:
        if self._reader_fd is None or self._callback is None or self._connection is None:
            return
        try:
            data = os.read(self._reader_fd, 65536)
        except BlockingIOError:
            return
        if not data:
            return
        result = self._callback(self._connection, data)
        if inspect.isawaitable(result):
            task = asyncio.create_task(result)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def close(self) -> None:
        if self._loop is not None and self._reader_fd is not None:
            self._loop.remove_reader(self._reader_fd)
        for task in list(self._tasks):
            task.cancel()
        for fd in (self._reader_fd, self._writer_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._reader_fd = None
        self._writer_fd = None
        self._connection = None
