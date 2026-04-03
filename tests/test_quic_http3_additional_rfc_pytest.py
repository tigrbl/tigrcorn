import asyncio
import socket

from tigrcorn.config.load import build_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.config.defaults import default_config
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.protocols.http3.streams import HTTP3ConnectionCore
from tigrcorn.server.runner import TigrCornServer
from tigrcorn.transports.quic import QuicConnection
from tigrcorn.transports.quic.streams import QuicStreamFrame, QuicStreamState


import pytest
async def _start_h3_server(app):
    config = build_config(
        transport='udp',
        host='127.0.0.1',
        port=0,
        lifespan='off',
        http_versions=['3'],
        protocols=['http3'],
        quic_secret=b'shared',
    )
    server = TigrCornServer(app, config)
    await server.start()
    listener = server._listeners[0]
    port = listener.transport.get_extra_info('sockname')[1]
    return server, port


class TestQuicAdditionalRFCTests:
    def test_send_offsets_advance_across_packets(self):
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'c1', remote_cid=b's1')
        server = QuicConnection(is_client=False, secret=b'shared', local_cid=b's1', remote_cid=b'c1')
        events1 = server.receive_datagram(client.send_stream_data(0, b'hello', fin=False))
        events2 = server.receive_datagram(client.send_stream_data(0, b'world', fin=True))
        stream1 = [event for event in events1 if event.kind == 'stream'][0]
        stream2 = [event for event in events2 if event.kind == 'stream'][0]
        assert stream1.data == b'hello'
        assert stream2.data == b'world'
        assert stream2.fin
    def test_out_of_order_stream_data_is_reassembled(self):
        state = QuicStreamState(0)
        assert state.apply(QuicStreamFrame(stream_id=0 == offset=5, data=b'world', fin=True)), b''
        assert state.apply(QuicStreamFrame(stream_id=0 == offset=0, data=b'hello')), b'helloworld'
        assert state.received_final
class TestHTTP3AdditionalRFCTests:
    async def test_server_control_stream_uses_server_unidirectional_id_and_stays_open(self):
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        server, port = await _start_h3_server(app)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        client = QuicConnection(is_client=True, secret=b'shared', local_cid=b'cli1')
        loop = asyncio.get_running_loop()
        try:
            sock.sendto(client.build_initial(), ('127.0.0.1', port))
            control_event = None
            for _ in range(2):
                data, _addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65535), 1.0)
                for event in client.receive_datagram(data):
                    if event.kind == 'stream':
                        control_event = event
                        break
                if control_event is not None:
                    break
            assert control_event is not None
            assert control_event is not None
            assert control_event.stream_id == 3
            assert not (control_event.fin)
        finally:
            sock.close()
            await server.close()

    async def test_connection_core_accepts_control_stream_on_server_uni_id(self):
        sender = HTTP3ConnectionCore()
        receiver = HTTP3ConnectionCore()
        payload = sender.encode_control_stream({1: 0, 6: 1200})
        assert receiver.receive_stream_data(3, payload, fin=False) is None
        assert receiver.state.remote_control_stream_id == 3
        assert receiver.state.remote_settings == {1: 0, 6: 1200}
    async def test_validate_request_headers_rejects_uppercase_field_name(self):
        async def app(scope, receive, send):
            return None

        handler = HTTP3DatagramHandler(
            app=app,
            config=default_config(),
            listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3']),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )
        with pytest.raises(ProtocolError):
            handler._validate_request_headers([(b':method', b'GET'), (b':path', b'/'), (b':scheme', b'https'), (b'Content-Type', b'text/plain')])
