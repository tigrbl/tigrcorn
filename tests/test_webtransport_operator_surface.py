import os
import unittest
from unittest.mock import patch

from tigrcorn.cli import build_parser
from tigrcorn.config.load import build_config, build_config_from_namespace, build_config_from_sources, config_from_mapping
from tigrcorn.errors import ConfigError


class WebTransportOperatorSurfaceTests(unittest.TestCase):
    def test_cli_protocol_webtransport_wires_h3_quic_and_tuning_flags(self) -> None:
        parser = build_parser()
        namespace = parser.parse_args(
            [
                "tests.fixtures_pkg.appmod:app",
                "--transport",
                "udp",
                "--protocol",
                "webtransport",
                "--webtransport-max-sessions",
                "8",
                "--webtransport-max-streams",
                "64",
                "--webtransport-max-datagram-size",
                "1200",
                "--webtransport-origin",
                "https://example.test,https://api.example.test",
                "--webtransport-path",
                "wt",
            ]
        )

        config = build_config_from_namespace(namespace)
        listener = config.listeners[0]

        self.assertEqual(listener.kind, "udp")
        self.assertEqual(listener.enabled_protocols, ("quic", "http3", "webtransport"))
        self.assertIn("3", listener.http_versions)
        self.assertEqual(config.webtransport.max_sessions, 8)
        self.assertEqual(config.webtransport.max_streams, 64)
        self.assertEqual(config.webtransport.max_datagram_size, 1200)
        self.assertEqual(config.webtransport.origins, ["https://example.test", "https://api.example.test"])
        self.assertEqual(config.webtransport.path, "/wt")

    def test_config_mapping_accepts_webtransport_block(self) -> None:
        config = config_from_mapping(
            {
                "listeners": [{"kind": "udp", "protocols": ["webtransport"]}],
                "webtransport": {
                    "max_sessions": "2",
                    "max_streams": "16",
                    "max_datagram_size": "900",
                    "origins": "https://example.test",
                    "path": "/transport",
                },
            }
        )

        self.assertEqual(config.listeners[0].enabled_protocols, ("quic", "http3", "webtransport"))
        self.assertEqual(config.webtransport.max_sessions, 2)
        self.assertEqual(config.webtransport.max_streams, 16)
        self.assertEqual(config.webtransport.max_datagram_size, 900)
        self.assertEqual(config.webtransport.origins, ["https://example.test"])
        self.assertEqual(config.webtransport.path, "/transport")

    def test_env_vars_configure_webtransport_tuning(self) -> None:
        with patch.dict(
            os.environ,
            {
                "WT_PROTOCOL": "webtransport",
                "WT_TRANSPORT": "udp",
                "WT_WEBTRANSPORT_MAX_SESSIONS": "3",
                "WT_WEBTRANSPORT_MAX_STREAMS": "24",
                "WT_WEBTRANSPORT_MAX_DATAGRAM_SIZE": "1000",
                "WT_WEBTRANSPORT_ORIGIN": "https://one.test,https://two.test",
                "WT_WEBTRANSPORT_PATH": "wt",
            },
            clear=False,
        ):
            config = build_config_from_sources(env_prefix="WT")

        self.assertEqual(config.listeners[0].enabled_protocols, ("quic", "http3", "webtransport"))
        self.assertEqual(config.webtransport.max_sessions, 3)
        self.assertEqual(config.webtransport.max_streams, 24)
        self.assertEqual(config.webtransport.max_datagram_size, 1000)
        self.assertEqual(config.webtransport.origins, ["https://one.test", "https://two.test"])
        self.assertEqual(config.webtransport.path, "/wt")

    def test_public_api_accepts_webtransport_tuning(self) -> None:
        config = build_config(
            transport="udp",
            protocols=["webtransport"],
            webtransport_max_sessions=4,
            webtransport_max_streams=32,
            webtransport_max_datagram_size=1100,
            webtransport_origins=["https://example.test"],
            webtransport_path="/wt",
        )

        self.assertEqual(config.listeners[0].enabled_protocols, ("quic", "http3", "webtransport"))
        self.assertEqual(config.webtransport.max_sessions, 4)
        self.assertEqual(config.webtransport.max_streams, 32)
        self.assertEqual(config.webtransport.max_datagram_size, 1100)
        self.assertEqual(config.webtransport.origins, ["https://example.test"])
        self.assertEqual(config.webtransport.path, "/wt")

    def test_webtransport_fails_closed_on_non_udp_listener(self) -> None:
        with self.assertRaisesRegex(ConfigError, "webtransport requires an udp listener"):
            config_from_mapping({"listeners": [{"kind": "tcp", "protocols": ["webtransport"]}]})


if __name__ == "__main__":
    unittest.main()
