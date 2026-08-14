from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path

import pytest
import tomllib
from tigrcorn_config.load.mapping import config_from_mapping
from tigrcorn_quic_cc import (
    API_VERSION,
    AckReceived,
    ControllerContext,
    ControllerSnapshot,
    DeterministicClock,
    PacketInfo,
    PacketsLost,
    PersistentCongestion,
    ProviderCompatibilityError,
    ProviderDiscoveryError,
    ProviderMetadata,
    ProviderRegistry,
    SendLimits,
)
from tigrcorn_quic_cc_reno import factory as reno_factory
from tigrcorn_runtime.cli import build_parser
from tigrcorn_runtime.server.runner import TigrCornServer
from tigrcorn_transports.quic.congestion import QuicCongestionRuntime
from tigrcorn_transports.quic.connection import QuicConnection

ROOT = Path(__file__).resolve().parents[1]


class _EntryPoint:
    def __init__(self, name: str, value: object) -> None:
        self.name = name
        self._value = value
        self.loads = 0

    def load(self) -> object:
        self.loads += 1
        return self._value


class _Controller:
    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = invalid

    def on_packet_sent(self, event: object) -> None: pass
    def on_ack_received(self, event: object) -> None: pass
    def on_packets_lost(self, event: object) -> None: pass
    def on_persistent_congestion(self, event: object) -> None: pass
    def on_ecn_feedback(self, event: object) -> None: pass
    def on_mtu_updated(self, event: object) -> None: pass

    def send_limits(self, now: float) -> SendLimits:
        return SendLimits(
            congestion_window=0 if self.invalid else 12_000,
            pacing_rate=12_000.0,
            send_quantum=1_200,
        )

    def snapshot(self) -> ControllerSnapshot:
        return ControllerSnapshot("test", "steady", 12_000, 12_000.0, 1_200)


class _Factory:
    metadata = ProviderMetadata("test", "Test", "test-provider", "1.0")

    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = invalid
        self.created = 0

    def validate_options(self, options: Mapping[str, object]) -> Mapping[str, object]:
        return dict(options)

    def create(self, context: ControllerContext, options: Mapping[str, object], *, clock=None) -> _Controller:
        self.created += 1
        return _Controller(invalid=self.invalid)


def _packet(number: int, sent_time: float = 1.0) -> PacketInfo:
    return PacketInfo(number, sent_time, 1_200)


def test_api_v1_events_are_immutable_and_use_versioned_entrypoint() -> None:
    event = AckReceived(1.1, (_packet(1),), 1_200, 0, 0.1, 0.1, 0.1, 0.05)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.bytes_acked = 0  # type: ignore[misc]
    assert API_VERSION == "1"


def test_registry_is_lazy_and_rejects_missing_and_duplicate_ids() -> None:
    selected = _EntryPoint("test", _Factory())
    untouched = _EntryPoint("other", _Factory())
    registry = ProviderRegistry(entry_points=[selected, untouched])
    assert registry.resolve("test").metadata.algorithm_id == "test"
    assert selected.loads == 1
    assert untouched.loads == 0
    with pytest.raises(ProviderDiscoveryError):
        registry.resolve("missing")
    with pytest.raises(ProviderDiscoveryError):
        ProviderRegistry(entry_points=[selected, _EntryPoint("test", _Factory())]).resolve("test")


def test_registry_rejects_incompatible_provider_api() -> None:
    factory = _Factory()
    factory.metadata = dataclasses.replace(factory.metadata, api_version="2")
    with pytest.raises(ProviderCompatibilityError):
        ProviderRegistry(builtins={"test": factory}).resolve("test")


def test_config_precedence_cli_and_listener_override() -> None:
    config = config_from_mapping(
        {
            "quic": {
                "congestion_control": {
                    "algorithm": "reno",
                    "options": {"pacing_gain": 1.1, "initial_window_packets": 8},
                }
            },
            "listeners": [
                {
                    "kind": "udp",
                    "http_versions": ["3"],
                    "congestion_control": {
                        "options": {"initial_window_packets": 12}
                    },
                }
            ],
        }
    )
    selected = config.listeners[0].congestion_control
    assert selected is not None
    assert selected.algorithm == "reno"
    assert selected.options == {"pacing_gain": 1.1, "initial_window_packets": 12}

    ns = build_parser().parse_args(
        [
            "example:app",
            "--quic-congestion-control",
            "reno",
            "--quic-congestion-control-options",
            '{"pacing_gain": 1.25}',
        ]
    )
    assert ns.quic_congestion_control == "reno"
    assert ns.quic_congestion_control_options == {"pacing_gain": 1.25}


def test_each_network_path_gets_a_fresh_controller() -> None:
    factory = _Factory()
    connection = QuicConnection(
        congestion_controller_factory=factory,
        congestion_controller_options={"mode": "test"},
    )
    default = connection.recovery.congestion.controller
    migrated = connection._path_state(("127.0.0.1", 4433)).recovery.congestion.controller
    assert default is not migrated
    assert factory.created == 2


def test_invalid_controller_output_fails_closed() -> None:
    runtime = QuicCongestionRuntime(max_datagram_size=1_200, factory=_Factory())
    runtime.controller.invalid = True  # type: ignore[attr-defined]
    assert runtime.limits(now=1.0) is None
    assert runtime.failed is True
    assert runtime.can_send(1_200, bytes_in_flight=0, now=1.0) is False


def test_reno_golden_trace_preserves_window_transitions() -> None:
    clock = DeterministicClock(1.0)
    controller = reno_factory.create(
        ControllerContext(max_datagram_size=1_200),
        reno_factory.validate_options({}),
        clock=clock,
    )
    assert controller.send_limits(clock()).congestion_window == 12_000
    controller.on_ack_received(
        AckReceived(1.1, (_packet(1),), 1_200, 0, 0.1, 0.1, 0.1, 0.05)
    )
    assert controller.send_limits(1.1).congestion_window == 13_200
    controller.on_packets_lost(PacketsLost(1.2, (_packet(2, 1.15),), 1_200, 0, "application"))
    assert controller.send_limits(1.2).congestion_window == 6_600
    controller.on_persistent_congestion(PersistentCongestion(2.0, "application", 1.0))
    assert controller.send_limits(2.0).congestion_window == 2_400


def test_package_dependency_dag_and_entrypoint_are_declared() -> None:
    contract = tomllib.loads((ROOT / "pkgs/tigrcorn-quic-cc/pyproject.toml").read_text("utf-8"))
    reno = tomllib.loads((ROOT / "pkgs/tigrcorn-quic-cc-reno/pyproject.toml").read_text("utf-8"))
    assert contract["project"].get("dependencies", []) == []
    assert reno["project"]["entry-points"]["tigrcorn.quic_cc.v1"]["reno"] == "tigrcorn_quic_cc_reno:factory"


async def _app(scope, receive, send) -> None:
    return None


def test_runtime_describe_reports_effective_algorithm_with_redaction() -> None:
    config = config_from_mapping(
        {
            "quic": {
                "congestion_control": {
                    "algorithm": "reno",
                    "options": {"pacing_gain": 1.2, "api_token": "do-not-show"},
                }
            },
            "listeners": [{"kind": "udp", "http_versions": ["3"]}],
        }
    )
    listener = TigrCornServer(_app, config).describe()["listeners"][0]
    assert listener["quic_congestion_control"] == {
        "algorithm": "reno",
        "options": {"pacing_gain": 1.2, "api_token": "<redacted>"},
        "resolved_provider": None,
    }
