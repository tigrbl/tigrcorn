import asyncio
import os
import tempfile

from tigrcorn.listeners.inproc import InProcListener
from tigrcorn.listeners.pipe import PipeListener


import pytest

async def test_inproc_listener_dispatch():
    seen = []

    async def handler(data):
        seen.append(data)

    listener = InProcListener()
    await listener.start(handler)
    await listener.dispatch(b'payload')
    await listener.close()
    assert seen == [b'payload']
@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='named pipes unavailable')
async def test_pipe_listener_start_close():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'sock.pipe')
        listener = PipeListener(path)
        events = []

        async def handler(connection, data):
            events.append((connection.path, data))

        await listener.start(handler)
        assert os.path.exists(path)
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, b'payload')
            await asyncio.sleep(0.05)
        finally:
            os.close(fd)
        await listener.close()
        assert events == [(path, b'payload')]