import asyncio

from tigrcorn.protocols.custom.adapters import adapt_inbound, adapt_outbound, adapt_scope
from tigrcorn.transports.inproc.channel import InProcChannel
from tigrcorn.transports.tcp.reader import PrebufferedReader


import pytest
class TestPrebufferedAndCustomTests:
    async def test_prebuffered_reader(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'world\nrest')
        reader.feed_eof()
        wrapped = PrebufferedReader(reader, b'hello ')
        assert await wrapped.readuntil(b'\n') == b'hello world\n'
        assert await wrapped.read() == b'rest'
    async def test_inproc_channel_and_custom_adapters(self):
        channel = InProcChannel(capacity=1)
        await channel.send(b'data')
        assert await channel.recv() == b'data'
        scope = adapt_scope({'type': 'tigrcorn.stream'})
        assert 'tigrcorn.custom' in scope['extensions']
        assert adapt_inbound(b'a')['type'] == 'tigrcorn.stream.receive'
        assert adapt_outbound(b'b')['type'] == 'tigrcorn.stream.send'