import asyncio
import unittest

from tigrcorn.protocols.custom.adapters import adapt_inbound, adapt_outbound, adapt_scope
from tigrcorn.transports.inproc.channel import InProcChannel
from tigrcorn.transports.tcp.reader import PrebufferedReader


class PrebufferedAndCustomTests(unittest.IsolatedAsyncioTestCase):
    async def test_prebuffered_reader(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'world\nrest')
        reader.feed_eof()
        wrapped = PrebufferedReader(reader, b'hello ')
        self.assertEqual(await wrapped.readuntil(b'\n'), b'hello world\n')
        self.assertEqual(await wrapped.read(), b'rest')

    async def test_inproc_channel_and_custom_adapters(self):
        channel = InProcChannel(capacity=1)
        await channel.send(b'data')
        self.assertEqual(await channel.recv(), b'data')
        scope = adapt_scope({'type': 'tigrcorn.stream'})
        self.assertIn('tigrcorn.custom', scope['extensions'])
        self.assertEqual(adapt_inbound(b'a')['type'], 'tigrcorn.stream.receive')
        self.assertEqual(adapt_outbound(b'b')['type'], 'tigrcorn.stream.send')
