from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tigrcorn.compat.interop_runner import generate_observer_qlog
from tigrcorn.config.defaults import default_config
from tigrcorn.config.env import load_env_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.config.observability_surface import QLOG_EXPERIMENTAL_SCHEMA_VERSION
from tigrcorn.config.quic_surface import QUIC_STATE_CLAIMS
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.observability.metrics import Metrics
from tigrcorn.protocols.http3.codec import (
    H3_SETTINGS_ERROR,
    SETTING_H3_DATAGRAM,
    HTTP3ConnectionError,
    decode_settings,
    encode_settings,
)
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.security.tls13.extensions import (
    decode_early_data,
    decode_pre_shared_key_client,
)
from tigrcorn.security.tls13.handshake import TlsAlertError
from tigrcorn.transports.quic.crypto import (
    compute_retry_integrity_tag,
    derive_initial_packet_protection_keys,
    update_quic_secret,
)
from tigrcorn.transports.quic.handshake import QuicTlsHandshakeDriver, generate_self_signed_certificate
from tigrcorn.transports.quic.recovery import QuicLossRecovery
from tigrcorn.transports.quic.streams import (
    FRAME_DATAGRAM,
    QuicConnectionCloseFrame,
    QuicDatagramFrame,
    QuicPathChallengeFrame,
    decode_frame,
    encode_frame,
    validate_frame_for_packet_space,
)
from tigrcorn.utils.bytes import encode_quic_varint


ROOT = Path(__file__).resolve().parents[1]


def _http3_handler(app=None) -> HTTP3DatagramHandler:
    async def default_app(scope, receive, send):
        return None

    return HTTP3DatagramHandler(
        app=app or default_app,
        config=default_config(),
        listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3']),
        access_logger=AccessLogger(configure_logging('warning'), enabled=False),
    )


class GovernedRFCDeepCoverageTests(unittest.IsolatedAsyncioTestCase):
    def test_rfc9000_packet_space_legality_and_rfc9221_datagram_rules(self) -> None:
        datagram = QuicDatagramFrame(b'payload')
        validate_frame_for_packet_space(datagram, 'application')
        validate_frame_for_packet_space(datagram, '0rtt')
        for packet_space in ('initial', 'handshake'):
            with self.subTest(packet_space=packet_space):
                with self.assertRaises(ProtocolError):
                    validate_frame_for_packet_space(datagram, packet_space)

        application_close = QuicConnectionCloseFrame(error_code=7, application=True)
        validate_frame_for_packet_space(application_close, 'application')
        for packet_space in ('initial', 'handshake'):
            with self.subTest(application_close_space=packet_space):
                with self.assertRaises(ProtocolError):
                    validate_frame_for_packet_space(application_close, packet_space)

        validate_frame_for_packet_space(QuicPathChallengeFrame(b'12345678'), 'application')
        with self.assertRaises(ProtocolError):
            validate_frame_for_packet_space(QuicPathChallengeFrame(b'12345678'), '0rtt')

        length_present = encode_frame(QuicDatagramFrame(b'abc'))
        decoded, offset = decode_frame(length_present)
        self.assertEqual(offset, len(length_present))
        self.assertIsInstance(decoded, QuicDatagramFrame)
        self.assertEqual(decoded.data, b'abc')

        length_absent = encode_quic_varint(FRAME_DATAGRAM) + b'raw-datagram'
        decoded, offset = decode_frame(length_absent)
        self.assertEqual(offset, len(length_absent))
        self.assertIsInstance(decoded, QuicDatagramFrame)
        self.assertEqual(decoded.data, b'raw-datagram')

    def test_rfc9001_retry_integrity_and_key_update_separation(self) -> None:
        original_dcid = bytes.fromhex('8394c8f03e515708')
        retry_without_tag = bytes.fromhex('ff000000010008f067a5502a4262b5746f6b656e')
        correct_tag = compute_retry_integrity_tag(retry_without_tag, original_dcid)
        wrong_tag = compute_retry_integrity_tag(retry_without_tag, b'wrongcid')
        self.assertNotEqual(wrong_tag, correct_tag)

        client, server = derive_initial_packet_protection_keys(original_dcid)
        self.assertNotEqual(client.key, server.key)
        self.assertNotEqual(client.iv, server.iv)
        self.assertNotEqual(client.hp, server.hp)

        secret = bytes.fromhex('9ac312a7f877468ebe69422748ad00a15443f18203a07d6060f688f30f21632b')
        first_update = update_quic_secret(secret)
        second_update = update_quic_secret(first_update)
        self.assertNotEqual(first_update, secret)
        self.assertNotEqual(second_update, first_update)

    def test_rfc9002_recovery_ack_delay_pto_and_persistent_congestion(self) -> None:
        recovery = QuicLossRecovery(max_datagram_size=1200)
        recovery.rtt.smoothed_rtt = 0.1
        recovery.rtt.latest_rtt = 0.1
        recovery.rtt.rttvar = 0.02
        recovery.rtt.initialized = True
        self.assertAlmostEqual(recovery.pto_timeout(packet_space='application'), 0.205)
        self.assertAlmostEqual(recovery.pto_timeout(packet_space='initial'), 0.18)

        recovery.on_packet_sent(1, 1200, sent_time=1.0)
        first_deadline = recovery.next_pto_deadline(now=1.0)
        recovery.on_pto_expired()
        second_deadline = recovery.next_pto_deadline(now=1.0)
        self.assertIsNotNone(first_deadline)
        self.assertIsNotNone(second_deadline)
        assert first_deadline is not None and second_deadline is not None
        self.assertGreater(second_deadline, first_deadline)

        delayed = QuicLossRecovery(max_datagram_size=1200)
        delayed.on_packet_sent(1, 1200, sent_time=1.0)
        delayed.on_ack_received([1], now=1.1)
        delayed.on_packet_sent(2, 1200, sent_time=1.2)
        delayed.on_ack_received([2], now=1.35, ack_delay=0.1)
        self.assertAlmostEqual(delayed.rtt.smoothed_rtt, 0.103125)

        persistent = QuicLossRecovery(max_datagram_size=1200)
        persistent.rtt.smoothed_rtt = 0.01
        persistent.rtt.latest_rtt = 0.01
        persistent.rtt.rttvar = 0.001
        persistent.rtt.initialized = True
        persistent.on_packet_sent(0, 1200, sent_time=0.0)
        persistent.on_ack_received([0], now=0.1)
        for packet_number, sent_at in ((1, 0.2), (2, 1.0), (3, 2.0), (4, 3.0)):
            persistent.on_packet_sent(packet_number, 1200, sent_time=sent_at)
        lost = persistent.on_ack_received([4], now=3.2)
        self.assertEqual(lost, [1, 2, 3])
        self.assertTrue(persistent.persistent_congestion)
        self.assertEqual(persistent.congestion_window, persistent.minimum_congestion_window)

    def test_rfc9114_request_control_strictness_and_h3_datagram_settings(self) -> None:
        handler = _http3_handler()
        with self.assertRaises(ProtocolError):
            handler._validate_request_headers(
                [(b':method', b'GET'), (b'x-seen', b'1'), (b':path', b'/'), (b':scheme', b'https')]
            )
        with self.assertRaises(ProtocolError):
            handler._validate_request_headers([(b':method', b'GET'), (b':scheme', b'https')])

        settings_payload = encode_settings({SETTING_H3_DATAGRAM: 1})
        self.assertEqual(decode_settings(settings_payload), {SETTING_H3_DATAGRAM: 1})

        duplicate = (
            encode_quic_varint(SETTING_H3_DATAGRAM)
            + encode_quic_varint(1)
            + encode_quic_varint(SETTING_H3_DATAGRAM)
            + encode_quic_varint(1)
        )
        with self.assertRaises(HTTP3ConnectionError) as duplicate_ctx:
            decode_settings(duplicate)
        self.assertEqual(duplicate_ctx.exception.error_code, H3_SETTINGS_ERROR)

        with self.assertRaises(HTTP3ConnectionError) as reserved_ctx:
            decode_settings(encode_quic_varint(0x00) + encode_quic_varint(1))
        self.assertEqual(reserved_ctx.exception.error_code, H3_SETTINGS_ERROR)

    def test_rfc8446_quic_tls_rejection_paths(self) -> None:
        with self.assertRaises(ProtocolError):
            decode_early_data(b'\x00', 'client_hello')
        with self.assertRaises(ProtocolError):
            decode_early_data(b'\x00', 'new_session_ticket')

        mismatched_psk = b'\x00\x08\x00\x02id\x00\x00\x00\x00\x00\x00'
        with self.assertRaises(ProtocolError):
            decode_pre_shared_key_client(mismatched_psk)

        cert_pem, key_pem = generate_self_signed_certificate('server.example')
        client = QuicTlsHandshakeDriver(
            is_client=True,
            alpn='h2',
            server_name='server.example',
            trusted_certificates=[cert_pem],
        )
        server = QuicTlsHandshakeDriver(
            is_client=False,
            alpn='h3',
            server_name='server.example',
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
        )
        with self.assertRaises(TlsAlertError):
            server.receive(client.initiate())

    def test_rfc9297_http_datagram_carrier_mapping_and_limits(self) -> None:
        handler = object.__new__(HTTP3DatagramHandler)
        handler.config = SimpleNamespace(webtransport=SimpleNamespace(max_datagram_size=3))
        handler.listener = SimpleNamespace(max_datagram_size=1200)

        payload = handler._encode_webtransport_datagram_payload(12, b'abc')
        stream_id, data = handler._decode_webtransport_datagram_payload(payload)
        self.assertEqual(SETTING_H3_DATAGRAM, 0x33)
        self.assertEqual(stream_id, 12)
        self.assertEqual(data, b'abc')

        with self.assertRaises(ProtocolError):
            handler._encode_webtransport_datagram_payload(12, b'abcd')

    async def test_rfc8470_and_rfc9114_section_10_9_emit_425_before_asgi_dispatch(self) -> None:
        app_called = False

        async def app(scope, receive, send):
            nonlocal app_called
            app_called = True

        config = default_config()
        config.quic.early_data_policy = 'require'
        handler = HTTP3DatagramHandler(
            app=app,
            config=config,
            listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3']),
            access_logger=AccessLogger(configure_logging('warning'), enabled=False),
        )
        captured: dict[str, object] = {}

        def fake_response(session, stream_id, status, headers, body, *, end_stream):
            captured['status'] = status
            captured['body'] = body
            captured['end_stream'] = end_stream
            return [b'h3-response']

        handler._build_http3_response_datagrams_locked = fake_response  # type: ignore[method-assign]
        session = SimpleNamespace(
            addr=('127.0.0.1', 5555),
            quic=SimpleNamespace(handshake_driver=SimpleNamespace(_using_psk=True, early_data_accepted=False)),
            stream_work_leases={},
        )
        request_state = SimpleNamespace(
            headers=[
                (b':method', b'GET'),
                (b':path', b'/early'),
                (b':scheme', b'https'),
                (b':authority', b'example.com'),
            ],
            body=b'',
            trailers=[],
        )
        endpoint = SimpleNamespace(local_addr=('127.0.0.1', 4433))

        outbound = await handler._invoke_http_app(session, 0, request_state, endpoint)

        self.assertEqual(outbound, [b'h3-response'])
        self.assertFalse(app_called)
        self.assertEqual(captured['status'], 425)
        self.assertEqual(captured['body'], b'too early')
        self.assertTrue(captured['end_stream'])

    def test_rfc3986_request_target_path_query_and_authority_forms_are_preserved(self) -> None:
        handler = _http3_handler()
        request_state = SimpleNamespace(
            headers=[
                (b':method', b'GET'),
                (b':path', b'/encoded%2Fpath?x=y%20z&empty='),
                (b':scheme', b'https'),
                (b':authority', b'example.com'),
            ],
            body=b'',
        )
        header_map = handler._validate_request_headers(list(request_state.headers))
        request = handler._build_request(request_state, header_map)
        self.assertEqual(request.path, '/encoded%2Fpath')
        self.assertEqual(request.raw_path, b'/encoded%2Fpath')
        self.assertEqual(request.query_string, b'x=y%20z&empty=')

        connect_state = SimpleNamespace(headers=[(b':method', b'CONNECT'), (b':authority', b'example.com:443')], body=b'')
        connect_map = handler._validate_request_headers(list(connect_state.headers))
        connect_request = handler._build_request(connect_state, connect_map)
        self.assertEqual(connect_request.target, 'example.com:443')
        self.assertEqual(connect_request.path, 'example.com:443')
        self.assertEqual(connect_request.query_string, b'')

    def test_rfc9308_quic_applicability_profile_is_exposed_in_config_and_state(self) -> None:
        payload = load_env_config(
            'TIGRCORN',
            environ={
                'TIGRCORN_QUIC_REQUIRE_RETRY': 'true',
                'TIGRCORN_QUIC_MAX_DATAGRAM_SIZE': '1350',
                'TIGRCORN_QUIC_IDLE_TIMEOUT': '12.5',
                'TIGRCORN_QUIC_EARLY_DATA_POLICY': 'allow',
                'TIGRCORN_WEBTRANSPORT_MAX_DATAGRAM_SIZE': '512',
            },
        )
        self.assertTrue(payload['quic']['require_retry'])
        self.assertEqual(payload['quic']['max_datagram_size'], 1350)
        self.assertEqual(payload['quic']['idle_timeout'], 12.5)
        self.assertEqual(payload['quic']['early_data_policy'], 'allow')
        self.assertEqual(payload['webtransport']['max_datagram_size'], 512)

        state_features = {row['feature'] for row in QUIC_STATE_CLAIMS}
        self.assertGreaterEqual(state_features, {'retry', 'migration', 'zero_rtt'})

    def test_rfc9312_manageability_counters_and_qlog_redaction_are_stable(self) -> None:
        metrics = Metrics()
        metrics.quic_datagram_received(11)
        metrics.quic_datagram_sent(7)
        metrics.quic_path_challenge_observed()
        metrics.quic_path_response_observed()
        metrics.quic_path_migrated()
        metrics.quic_early_data_observed(accepted=False)
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot['quic_datagrams_received'], 1)
        self.assertEqual(snapshot['quic_datagrams_sent'], 1)
        self.assertEqual(snapshot['quic_path_challenges'], 1)
        self.assertEqual(snapshot['quic_path_responses'], 1)
        self.assertEqual(snapshot['quic_path_migrations'], 1)
        self.assertEqual(snapshot['quic_early_data_rejected'], 1)

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            packet_trace = root / 'trace.jsonl'
            qlog_path = root / 'observer.qlog'
            packet_trace.write_text(
                json.dumps(
                    {
                        'timestamp': 1.0,
                        'direction': 'client_to_server',
                        'transport': 'udp',
                        'local': {'host': '127.0.0.1', 'port': 4433},
                        'remote': {'host': '192.0.2.10', 'port': 51515},
                        'length': 1200,
                        'payload_hex': 'c00000000108deadbeefcafebabe08aabbccddeeff00110102030405060708090a0b0c0d0e0f',
                    }
                )
                + '\n',
                encoding='utf-8',
            )
            generate_observer_qlog(
                packet_trace_path=packet_trace,
                qlog_path=qlog_path,
                title='rfc9312',
                protocol='http3',
                ip_family='ipv4',
                negotiation={'alpn': 'h3'},
            )
            payload = json.loads(qlog_path.read_text(encoding='utf-8'))

        self.assertEqual(payload['schema_version'], QLOG_EXPERIMENTAL_SCHEMA_VERSION)
        trace = payload['traces'][0]
        self.assertTrue(trace['common_fields']['tigrcorn_qlog']['experimental'])
        self.assertEqual(trace['common_fields']['tigrcorn_qlog']['redaction']['network_endpoints'], 'redacted')
        self.assertEqual(trace['events'][0][3]['server']['host'], 'redacted')


if __name__ == '__main__':
    unittest.main()
