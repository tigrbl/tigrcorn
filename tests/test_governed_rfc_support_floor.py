from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tigrcorn.config.defaults import default_config
from tigrcorn.config.model import ListenerConfig
from tigrcorn.config.quic_surface import EARLY_DATA_CONTRACT
from tigrcorn.errors import ProtocolError
from tigrcorn.observability.logging import AccessLogger, configure_logging
from tigrcorn.observability.metrics import Metrics
from tigrcorn.protocols.http3.codec import SETTING_H3_DATAGRAM
from tigrcorn.protocols.http3.handler import HTTP3DatagramHandler
from tigrcorn.transports.quic.streams import FRAME_DATAGRAM, QuicDatagramFrame, decode_frame, encode_frame
from tigrcorn.ssot_baseline import iter_feature_baselines


ROOT = Path(__file__).resolve().parents[1]
TIER_RANK = {'T0': 0, 'T1': 1, 'T2': 2, 'T3': 3, 'T4': 4}
ACCEPTED_CLAIM_STATUSES = {'asserted', 'implemented', 'evidenced', 'certified', 'promoted', 'published'}
RFC_FEATURES = {
    'RFC 9112': 'feat:rfc-9112',
    'RFC 9000': 'feat:rfc-9000',
    'RFC 9001': 'feat:rfc-9001',
    'RFC 9002': 'feat:rfc-9002',
    'RFC 9114': 'feat:rfc-9114',
    'RFC 9204': 'feat:rfc-9204',
    'RFC 9221': 'feat:rfc-9221',
    'RFC 9312': 'feat:rfc-9312',
    'RFC 9308': 'feat:rfc-9308',
    'RFC 8446': 'feat:rfc-8446',
    'RFC 8470': 'feat:rfc-8470',
    'RFC 9114 Section 10.9': 'feat:rfc-9114-section-10-9',
    'RFC 9110 \u00a76.5': 'feat:rfc-9110-s6-5',
    'RFC 9297': 'feat:rfc-9297',
    'RFC 9220': 'feat:rfc-9220',
    'RFC 3986': 'feat:rfc-3986',
    'RFC 8441': 'feat:rfc-8441',
    'RFC 9113': 'feat:rfc-9113',
}


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))


def _by_id(rows: object) -> dict[str, dict[str, object]]:
    assert isinstance(rows, list)
    return {str(row['id']): row for row in rows if isinstance(row, dict)}


def _has_t012_baseline(registry: dict, feature_id: str) -> bool:
    baselines = {baseline.feature_id: baseline for baseline in iter_feature_baselines(registry)}
    return set(baselines[feature_id].claim_tiers) >= {'T0', 'T1', 'T2'}


def _http3_handler() -> HTTP3DatagramHandler:
    async def app(scope, receive, send):
        return None

    return HTTP3DatagramHandler(
        app=app,
        config=default_config(),
        listener=ListenerConfig(kind='udp', host='127.0.0.1', port=1, protocols=['http3']),
        access_logger=AccessLogger(configure_logging('warning'), enabled=False),
    )


class GovernedRFCSupportFloorTests(unittest.TestCase):
    def test_support_floor_has_governed_features_and_minimum_t2_claims(self) -> None:
        registry = _load_json('.ssot/registry.json')
        boundary = _load_json('docs/review/conformance/certification_boundary.json')
        features = _by_id(registry['features'])
        claims = _by_id(registry['claims'])

        adr_ids = {row['id'] for row in registry['adrs']}
        spec_ids = {row['id'] for row in registry['specs']}
        self.assertIn('adr:1037', adr_ids)
        self.assertIn('spc:2044', spec_ids)

        for rfc_name, feature_id in RFC_FEATURES.items():
            with self.subTest(rfc_name=rfc_name):
                self.assertIn(rfc_name, boundary['required_rfcs'])
                self.assertIn(rfc_name, boundary['required_rfc_evidence'])
                policy = boundary['required_rfc_evidence'][rfc_name]
                self.assertTrue(policy['declared_evidence'].get('local_conformance'), msg=rfc_name)

                feature = features[feature_id]
                self.assertTrue(_has_t012_baseline(registry, feature_id), msg=rfc_name)
                self.assertEqual(feature['plan']['horizon'], 'current')
                self.assertIn('spc:2044', feature['spec_ids'])
                self.assertGreaterEqual(TIER_RANK[feature['plan']['target_claim_tier']], TIER_RANK['T2'])

                linked_claims = [claims[claim_id] for claim_id in feature['claim_ids']]
                t2_or_stronger = [
                    claim
                    for claim in linked_claims
                    if TIER_RANK[claim['tier']] >= TIER_RANK['T2'] and claim['status'] in ACCEPTED_CLAIM_STATUSES
                ]
                self.assertTrue(t2_or_stronger, msg=rfc_name)

    def test_quic_datagram_frame_round_trips_for_rfc9221(self) -> None:
        self.assertEqual(FRAME_DATAGRAM, 0x30)

        raw = encode_frame(QuicDatagramFrame(b'payload'))
        decoded, offset = decode_frame(raw)

        self.assertEqual(offset, len(raw))
        self.assertIsInstance(decoded, QuicDatagramFrame)
        self.assertEqual(decoded.data, b'payload')

    def test_http_datagram_setting_and_payload_mapping_for_rfc9297(self) -> None:
        handler = object.__new__(HTTP3DatagramHandler)
        handler.config = SimpleNamespace(webtransport=SimpleNamespace(max_datagram_size=64))
        handler.listener = SimpleNamespace(max_datagram_size=1200)

        payload = handler._encode_webtransport_datagram_payload(8, b'abc')
        stream_id, data = handler._decode_webtransport_datagram_payload(payload)

        self.assertEqual(SETTING_H3_DATAGRAM, 0x33)
        self.assertEqual(stream_id, 8)
        self.assertEqual(data, b'abc')

    def test_early_data_policy_covers_rfc8470_and_http3_section_10_9(self) -> None:
        self.assertEqual(EARLY_DATA_CONTRACT['default_policy'], 'deny')
        self.assertEqual(EARLY_DATA_CONTRACT['value_space'], ['allow', 'deny', 'require'])
        self.assertIn('425 Too Early', EARLY_DATA_CONTRACT['replay_policy']['require_downgrade'])

        handler = object.__new__(HTTP3DatagramHandler)
        handler.config = SimpleNamespace(quic=SimpleNamespace(early_data_policy='require'))
        resumed = SimpleNamespace(quic=SimpleNamespace(handshake_driver=SimpleNamespace(_using_psk=True, early_data_accepted=False)))
        accepted = SimpleNamespace(quic=SimpleNamespace(handshake_driver=SimpleNamespace(_using_psk=True, early_data_accepted=True)))

        self.assertTrue(handler._should_send_too_early(resumed))
        self.assertFalse(handler._should_send_too_early(accepted))

    def test_uri_request_target_preservation_covers_rfc3986_floor(self) -> None:
        handler = _http3_handler()
        request_state = SimpleNamespace(
            headers=[
                (b':method', b'GET'),
                (b':path', b'/wt/stream?mode=datagram&n=1'),
                (b':scheme', b'https'),
                (b':authority', b'example.com'),
            ],
            body=b'',
        )

        header_map = handler._validate_request_headers(list(request_state.headers))
        request = handler._build_request(request_state, header_map)

        self.assertEqual(request.path, '/wt/stream')
        self.assertEqual(request.raw_path, b'/wt/stream')
        self.assertEqual(request.query_string, b'mode=datagram&n=1')

        connect_state = SimpleNamespace(headers=[(b':method', b'CONNECT'), (b':authority', b'example.com:443')], body=b'')
        connect_map = handler._validate_request_headers(list(connect_state.headers))
        connect_request = handler._build_request(connect_state, connect_map)
        self.assertEqual(connect_request.path, 'example.com:443')

        with self.assertRaises(ProtocolError):
            handler._validate_request_headers([(b':method', b'GET'), (b':scheme', b'https')])

    def test_quic_applicability_and_manageability_floor_is_operator_visible(self) -> None:
        metrics_schema = _load_json('docs/conformance/metrics_schema.json')
        quic_state = _load_json('docs/conformance/quic_state.json')

        families = metrics_schema['metrics_schema']['families']
        self.assertIn('quic_datagrams_received', families['transport'])
        self.assertIn('quic_datagrams_sent', families['transport'])
        self.assertIn('quic_path_migrations', families['loss'])
        self.assertIn('quic_early_data_attempted', families['security'])
        self.assertEqual(metrics_schema['qlog']['schema_version'], 'tigrcorn.qlog.experimental.v1')
        self.assertIn('migration', {row['feature'] for row in quic_state['claims']})
        self.assertIn('zero_rtt', {row['feature'] for row in quic_state['claims']})

        metrics = Metrics()
        metrics.quic_datagram_received(3)
        metrics.quic_datagram_sent(2)
        metrics.quic_early_data_observed(accepted=False)
        metrics.quic_path_migrated()
        snapshot = metrics.snapshot()

        self.assertEqual(snapshot['quic_datagrams_received'], 1)
        self.assertEqual(snapshot['quic_datagrams_sent'], 1)
        self.assertEqual(snapshot['quic_early_data_attempted'], 1)
        self.assertEqual(snapshot['quic_early_data_rejected'], 1)
        self.assertEqual(snapshot['quic_path_migrations'], 1)


if __name__ == '__main__':
    unittest.main()
