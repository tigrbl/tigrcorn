from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from tigrcorn.errors import ProtocolError, UnsupportedFeature
from tigrcorn.protocols.http1.parser import http11_request_head_error_matrix, read_http11_request_head
from tigrcorn.protocols.http1.serializer import http11_response_metadata_rules, response_allows_body
from tigrcorn.protocols.http2.state import H2StreamLifecycle, H2StreamState, h2_connection_rule_table, h2_stream_transition_table
from tigrcorn.protocols.http3.state import (
    HTTP3RequestPhase_DATA,
    HTTP3RequestPhase_INITIAL,
    HTTP3RequestPhase_TRAILERS,
    http3_control_stream_rule_table,
    http3_qpack_accounting_rule_table,
    http3_request_transition_table,
)
from tigrcorn.security.tls13.handshake import tls13_handshake_state_table
from tigrcorn.transports.quic.connection import quic_connection_state_table, quic_transport_error_matrix
from tigrcorn.transports.quic.recovery import quic_recovery_rule_table
from tigrcorn.transports.quic.streams import (
    FRAME_ACK,
    FRAME_PING,
    QuicConnectionCloseFrame,
    QuicHandshakeDoneFrame,
    QuicNewConnectionIdFrame,
    QuicPathChallengeFrame,
    quic_packet_space_legality_table,
    quic_packet_space_prohibitions,
    validate_frame_for_packet_space,
)
from tigrcorn.transports.tcp.reader import PrebufferedReader


class Phase3TransportCoreStrictnessCheckpointTests(unittest.TestCase):
    def test_http11_error_matrix_exports_core_cases(self):
        matrix = {entry['case']: entry for entry in http11_request_head_error_matrix()}
        for case in (
            'request_line_shape',
            'host_header_requirements',
            'transfer_encoding_chain',
            'content_length_and_chunked_conflict',
            'chunked_body_syntax',
        ):
            self.assertIn(case, matrix)

    def test_http11_response_metadata_rules_cover_bodyless_statuses(self):
        selectors = {entry['selector']: entry for entry in http11_response_metadata_rules()}
        self.assertFalse(selectors['1xx']['allows_body'])
        self.assertFalse(selectors['204']['allows_body'])
        self.assertFalse(response_allows_body(103))
        self.assertFalse(response_allows_body(204))
        self.assertFalse(response_allows_body(304))
        self.assertTrue(response_allows_body(200))

    def test_http11_runtime_examples_match_exported_errors(self):
        async def invalid_request_line() -> None:
            reader = asyncio.StreamReader()
            reader.feed_data(b'GET /missing-version\r\nHost: example.com\r\n\r\n')
            reader.feed_eof()
            with self.assertRaises(ProtocolError):
                await read_http11_request_head(PrebufferedReader(reader))

        async def missing_host() -> None:
            reader = asyncio.StreamReader()
            reader.feed_data(b'GET / HTTP/1.1\r\n\r\n')
            reader.feed_eof()
            with self.assertRaises(ProtocolError):
                await read_http11_request_head(PrebufferedReader(reader))

        async def unsupported_te_chain() -> None:
            reader = asyncio.StreamReader()
            reader.feed_data(
                b'POST /upload HTTP/1.1\r\n'
                b'Host: example.com\r\n'
                b'Transfer-Encoding: gzip, chunked\r\n\r\n'
            )
            reader.feed_eof()
            with self.assertRaises(UnsupportedFeature):
                await read_http11_request_head(PrebufferedReader(reader))

        asyncio.run(invalid_request_line())
        asyncio.run(missing_host())
        asyncio.run(unsupported_te_chain())

    def test_http2_transition_table_matches_lifecycle_methods(self):
        transitions = list(h2_stream_transition_table())
        self.assertIn({'from': 'idle', 'event': 'remote headers', 'to': 'open', 'notes': 'peer opens the stream without END_STREAM'}, transitions)
        self.assertTrue(any(entry['to'] == 'closed' for entry in transitions))

        state = H2StreamState(1)
        self.assertEqual(state.lifecycle, H2StreamLifecycle.IDLE)
        state.open_remote(end_stream=False)
        self.assertEqual(state.lifecycle, H2StreamLifecycle.OPEN)
        state.receive_end_stream()
        self.assertEqual(state.lifecycle, H2StreamLifecycle.HALF_CLOSED_REMOTE)
        state.send_end_stream()
        self.assertEqual(state.lifecycle, H2StreamLifecycle.CLOSED)

        rules = {entry['rule'] for entry in h2_connection_rule_table()}
        self.assertIn('first-frame-after-preface-is-settings', rules)
        self.assertIn('goaway-last-stream-id-monotonic', rules)

    def test_http3_request_control_and_qpack_tables_are_explicit(self):
        request_table = list(http3_request_transition_table())
        self.assertEqual(request_table[0]['from'], 'initial')
        self.assertTrue(any(entry['to'] == 'ready' for entry in request_table))
        self.assertEqual(HTTP3RequestPhase_INITIAL, 'initial')
        self.assertEqual(HTTP3RequestPhase_DATA, 'data')
        self.assertEqual(HTTP3RequestPhase_TRAILERS, 'trailers')

        control_rules = {entry['rule'] for entry in http3_control_stream_rule_table()}
        self.assertIn('single-control-stream', control_rules)
        self.assertIn('control-stream-begins-with-settings', control_rules)
        self.assertIn('goaway-id-must-not-increase', control_rules)

        qpack_rules = {entry['rule'] for entry in http3_qpack_accounting_rule_table()}
        self.assertIn('blocked-header-sections-are-retained', qpack_rules)
        self.assertIn('field-section-errors-map-to-decompression-failed', qpack_rules)

    def test_quic_packet_space_legality_exports_match_runtime_validator(self):
        table = quic_packet_space_legality_table()
        self.assertIn('PING', table['initial'])
        self.assertIn('CRYPTO', table['handshake'])
        self.assertNotIn('HANDSHAKE_DONE', table['initial'])

        validate_frame_for_packet_space(FRAME_PING, 'initial')
        validate_frame_for_packet_space(FRAME_ACK, 'handshake')

        with self.assertRaises(ProtocolError):
            validate_frame_for_packet_space(QuicHandshakeDoneFrame(), 'initial', is_client=False)
        with self.assertRaises(ProtocolError):
            validate_frame_for_packet_space(QuicHandshakeDoneFrame(), 'application', is_client=True)
        with self.assertRaises(ProtocolError):
            validate_frame_for_packet_space(QuicPathChallengeFrame(b'12345678'), '0rtt')
        with self.assertRaises(ProtocolError):
            validate_frame_for_packet_space(
                QuicNewConnectionIdFrame(sequence=1, retire_prior_to=0, connection_id=b'cid', stateless_reset_token=b'0' * 16),
                '0rtt',
            )
        with self.assertRaises(ProtocolError):
            validate_frame_for_packet_space(QuicConnectionCloseFrame(error_code=1, frame_type=0, reason='x', application=True), 'handshake')

        prohibitions = list(quic_packet_space_prohibitions())
        self.assertTrue(any(entry['packet_space'] == 'client-only' for entry in prohibitions))

    def test_quic_recovery_and_state_tables_exist(self):
        recovery_rules = {entry['rule'] for entry in quic_recovery_rule_table()}
        self.assertIn('packet-threshold-loss', recovery_rules)
        self.assertIn('pto-base', recovery_rules)
        self.assertIn('pacing-budget', recovery_rules)

        state_table = list(quic_connection_state_table())
        self.assertTrue(any(entry['to'] == 'established' for entry in state_table))
        self.assertTrue(any(entry['to'] == 'closed' for entry in state_table))

        error_matrix = {entry['name']: entry['code'] for entry in quic_transport_error_matrix()}
        self.assertIn('PROTOCOL_VIOLATION', error_matrix)
        self.assertIn('INVALID_TOKEN', error_matrix)

    def test_tls13_handshake_state_table_is_exported(self):
        table = list(tls13_handshake_state_table())
        self.assertTrue(any(entry['from'] == 'client_idle' and entry['to'] == 'client_wait_server' for entry in table))
        self.assertTrue(any(entry['to'] == 'complete' for entry in table))

    def test_generated_phase3_snapshot_files_exist(self):
        root = Path(__file__).resolve().parents[1] / 'docs' / 'review' / 'conformance' / 'phase3_transport_core'
        expected = [
            'http11_error_matrix.json',
            'http2_stream_transition_table.json',
            'http3_request_transition_table.json',
            'quic_packet_space_legality.json',
            'quic_recovery_rules.json',
            'tls13_handshake_state_table.json',
            'interop_evidence_manifest.json',
        ]
        for name in expected:
            path = root / name
            self.assertTrue(path.is_file(), name)
            payload = json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(payload)

        manifest = json.loads((root / 'interop_evidence_manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['scenario_classes']:
            artifact = Path(__file__).resolve().parents[1] / entry['artifact']
            self.assertTrue(artifact.is_file(), entry['artifact'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
