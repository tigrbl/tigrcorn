from __future__ import annotations

import json
from importlib import resources

import pytest

from tigrcorn import capabilities
from tigrcorn.cli import main as cli_main
from tigrcorn_config.profiles import list_blessed_profiles


def _records(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_records = payload["capabilities"]
    assert isinstance(raw_records, list)
    return {str(item["id"]): item for item in raw_records if isinstance(item, dict)}


def test_runtime_capability_registry_export_is_deterministic_and_json_serializable() -> None:
    first = capabilities.export()
    second = capabilities.export()

    assert first == second
    encoded = json.dumps(first, sort_keys=True)
    assert json.loads(encoded) == first
    assert first["schema_version"] == "1.0"
    assert first["registry"] == "tigrcorn.runtime-capabilities"
    assert first["profile"] == "default"

    records = _records(first)
    expected_ids = {
        "certification.deployment_profiles",
        "certification.release_validation",
        "protocol.http1",
        "protocol.http2",
        "protocol.http3",
        "protocol.websocket",
        "protocol.webtransport",
        "runtime.embedded",
        "runtime.lifecycle",
        "tls.alpn",
        "tls.ocsp",
        "tls.tls13",
        "transport.quic",
        "transport.tcp",
        "transport.udp",
    }
    assert expected_ids <= set(records)


def test_runtime_capability_state_taxonomy_is_stable() -> None:
    states = {record["state"] for record in _records(capabilities.export()).values()}

    assert states <= {state.value for state in capabilities.CapabilityState}
    assert {"compiled", "certified"} <= states


def test_runtime_capability_profile_validation_uses_blessed_profiles() -> None:
    assert "strict-h3-edge" in list_blessed_profiles()

    default_records = _records(capabilities.export(profile="default"))
    h3_records = _records(capabilities.export(profile="strict-h3-edge"))

    assert default_records["protocol.http1"]["enabled"] is True
    assert default_records["protocol.http3"]["enabled"] is False
    assert h3_records["protocol.http3"]["configured"] is True

    with pytest.raises(ValueError, match="unknown blessed profile"):
        capabilities.export(profile="does-not-exist")


def test_runtime_capability_schema_is_packaged_and_loadable() -> None:
    schema_text = resources.files("tigrcorn.capabilities.schema").joinpath(
        "runtime-capability-registry.schema.json"
    ).read_text(encoding="utf-8")
    schema = json.loads(schema_text)

    assert capabilities.load_schema() == schema
    assert schema["title"] == "Tigrcorn Runtime Capability Registry"
    assert schema["properties"]["registry"]["const"] == "tigrcorn.runtime-capabilities"


def test_runtime_capability_certified_and_enabled_are_separate() -> None:
    records = _records(capabilities.export(profile="default"))

    assert records["runtime.embedded"]["enabled"] is True
    assert records["runtime.embedded"]["certified"] is False
    assert records["runtime.embedded"]["state"] == "enabled"
    assert records["protocol.http1"]["enabled"] is True
    assert records["protocol.http1"]["certified"] is True
    assert records["protocol.http1"]["state"] == "certified"


def test_runtime_capability_unsupported_requirements_fail_closed() -> None:
    with pytest.raises(capabilities.UnsupportedCapabilityError, match="unsupported capability requirement"):
        capabilities.require_supported(["runtime.dag_execution"])

    with pytest.raises(capabilities.UnsupportedCapabilityError, match="protocol.http3"):
        capabilities.require_supported(["protocol.http3"], profile="default")


def test_cli_inspect_capabilities_json_outputs_registry(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["inspect", "capabilities", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == capabilities.export()
