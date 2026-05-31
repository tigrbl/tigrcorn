from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from tigrcorn.compat.interop_runner import generate_observer_qlog
from tigrcorn.config.observability_surface import QLOG_EXPERIMENTAL_SCHEMA_VERSION, observability_surface
from tigrcorn.observability.metrics import Metrics, OTEL_EXPORT_SCHEMA_VERSION, STATSD_EXPORT_SCHEMA_VERSION, parse_statsd_target
from tools.cert.observability_surface import generate as generate_observability_surface


@contextmanager
def _workspace_tempdir():
    with tempfile.TemporaryDirectory(dir='.') as tmp:
        yield Path(tmp).resolve()


class Phase6ObservabilitySurfaceTests(unittest.TestCase):
    def test_metrics_snapshot_exposes_phase6_counter_families(self) -> None:
        metrics = Metrics()
        metrics.connection_opened()
        metrics.quic_session_opened()
        metrics.quic_datagram_received(128)
        metrics.quic_datagram_sent(64)
        metrics.tls_handshake_completed()
        metrics.quic_retry_emitted()
        metrics.quic_early_data_observed(accepted=False)
        metrics.quic_path_challenge_observed()
        metrics.quic_path_response_observed()
        metrics.quic_path_migrated()
        metrics.quic_packets_lost_observed(3)
        metrics.quic_pto_expired()
        metrics.http3_request_served()
        metrics.http3_stream_reset()
        metrics.http3_goaway_observed()
        metrics.http3_qpack_encoder_stream_opened()
        metrics.http3_qpack_decoder_stream_opened()
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot['quic_datagrams_received'], 1)
        self.assertEqual(snapshot['quic_datagrams_sent'], 1)
        self.assertEqual(snapshot['tls_handshakes_completed'], 1)
        self.assertEqual(snapshot['quic_retry_sent'], 1)
        self.assertEqual(snapshot['quic_early_data_attempted'], 1)
        self.assertEqual(snapshot['quic_early_data_rejected'], 1)
        self.assertEqual(snapshot['quic_packets_lost'], 3)
        self.assertEqual(snapshot['quic_pto_expirations'], 1)
        self.assertEqual(snapshot['http3_requests_served'], 1)
        self.assertEqual(snapshot['http3_stream_resets'], 1)
        self.assertEqual(snapshot['http3_goaway_received'], 1)
        self.assertEqual(snapshot['http3_qpack_encoder_streams'], 1)
        self.assertEqual(snapshot['http3_qpack_decoder_streams'], 1)

    def test_statsd_target_parser_accepts_statsd_and_dogstatsd_schemes(self) -> None:
        self.assertEqual(parse_statsd_target('127.0.0.1:8125'), ('127.0.0.1', 8125, 'statsd'))
        self.assertEqual(parse_statsd_target('statsd://127.0.0.1:8125'), ('127.0.0.1', 8125, 'statsd'))
        self.assertEqual(parse_statsd_target('dogstatsd://127.0.0.1:8125'), ('127.0.0.1', 8125, 'dogstatsd'))

    def test_generated_artifacts_match_phase6_metadata(self) -> None:
        generate_observability_surface()
        payload = json.loads(Path('docs/conformance/metrics_schema.json').read_text(encoding='utf-8'))
        qlog = json.loads(Path('docs/conformance/qlog_experimental.json').read_text(encoding='utf-8'))
        metadata = observability_surface()
        self.assertEqual(payload['metrics_schema'], metadata['metrics_schema'])
        self.assertEqual(qlog['schema_version'], QLOG_EXPERIMENTAL_SCHEMA_VERSION)
        self.assertEqual(payload['export_adapters'][0]['schema_version'], STATSD_EXPORT_SCHEMA_VERSION)
        self.assertEqual(payload['export_adapters'][1]['schema_version'], OTEL_EXPORT_SCHEMA_VERSION)
        self.assertIn('dogstatsd://host:port', Path('docs/ops/observability.md').read_text(encoding='utf-8'))
        self.assertIn('qlog output is explicitly experimental', Path('docs/ops/observability.md').read_text(encoding='utf-8'))

    def test_qlog_output_is_redacted_and_versioned(self) -> None:
        with _workspace_tempdir() as root:
            packet_trace = root / 'trace.jsonl'
            qlog_path = root / 'observer.qlog'
            packet_trace.write_text(
                '\n'.join(
                    [
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
                    ]
                )
                + '\n',
                encoding='utf-8',
            )
            generate_observer_qlog(
                packet_trace_path=packet_trace,
                qlog_path=qlog_path,
                title='phase6',
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


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
