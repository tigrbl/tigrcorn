from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from tigrcorn.compat.interop_runner import (
    ExternalInteropRunner,
    InteropProcessSpec,
    _materialize_process_spec,
    build_environment_manifest,
    load_external_matrix,
    summarize_matrix_dimensions,
)

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
_TMPDIRS: list[tempfile.TemporaryDirectory] = []


def _write_matrix(payload: dict) -> Path:
    tmpdir = tempfile.TemporaryDirectory()
    _TMPDIRS.append(tmpdir)
    path = Path(tmpdir.name) / "matrix.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_matrix_and_dimension_summary() -> None:
    matrix_path = _write_matrix(
        {
            "name": "dimension-check",
            "scenarios": [
                {
                    "id": "http1-ipv4",
                    "protocol": "http1",
                    "role": "server",
                    "feature": "basic-get",
                    "peer": "fixture-http-client",
                    "ip_family": "ipv4",
                    "cipher_group": "tls13-aes128",
                    "sut": {
                        "name": "tigrcorn-http1",
                        "adapter": "subprocess",
                        "role": "server",
                        "command": [PYTHON, "-m", "tigrcorn", "examples.echo_http.app:app", "--host", "{bind_host}", "--port", "{bind_port}", "--protocol", "http1", "--disable-websocket", "--no-access-log", "--lifespan", "off"],
                        "ready_pattern": "listening on",
                        "version_command": [PYTHON, "-m", "tigrcorn", "--help"],
                    },
                    "peer_process": {
                        "name": "fixture-http-client",
                        "adapter": "subprocess",
                        "role": "client",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.interop_http_client"],
                        "version_command": [PYTHON, "-m", "tests.fixtures_pkg.interop_http_client", "--version"],
                    },
                },
                {
                    "id": "quic-ipv6",
                    "protocol": "quic",
                    "role": "client",
                    "feature": "observer-qlog",
                    "peer": "fixture-udp-echo",
                    "transport": "udp",
                    "ip_family": "ipv6",
                    "cipher_group": "x25519-aes128",
                    "retry": True,
                    "resumption": True,
                    "zero_rtt": True,
                    "key_update": True,
                    "migration": True,
                    "goaway": True,
                    "qpack_blocking": True,
                    "sut": {
                        "name": "fixture-quic-client",
                        "adapter": "subprocess",
                        "role": "client",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.interop_quic_client"],
                        "version_command": [PYTHON, "-m", "tests.fixtures_pkg.interop_quic_client", "--version"],
                    },
                    "peer_process": {
                        "name": "fixture-udp-echo",
                        "adapter": "subprocess",
                        "role": "server",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.interop_udp_echo_server"],
                        "ready_pattern": "READY",
                        "version_command": [PYTHON, "-m", "tests.fixtures_pkg.interop_udp_echo_server", "--version"],
                    },
                },
            ],
        }
    )
    matrix = load_external_matrix(matrix_path)
    dimensions = summarize_matrix_dimensions(matrix)
    assert matrix.name == "dimension-check"
    assert dimensions["protocol"] == ["http1", "quic"]
    assert dimensions["role"] == ["client", "server"]
    assert dimensions["ip_family"] == ["ipv4", "ipv6"]
    assert dimensions["retry"] == [False, True]
    assert dimensions["qpack_blocking"] == [False, True]
    assert dimensions["evidence_tier"] == ["mixed"]


def test_load_matrix_rejects_same_stack_peer_for_independent_certification() -> None:
    matrix_path = _write_matrix(
        {
            "name": "bad-independent-matrix",
            "metadata": {"evidence_tier": "independent_certification"},
            "scenarios": [
                {
                    "id": "bad-http3",
                    "protocol": "http3",
                    "role": "server",
                    "feature": "post-echo",
                    "peer": "tigrcorn-public-client",
                    "evidence_tier": "independent_certification",
                    "sut": {
                        "name": "tigrcorn-http3",
                        "adapter": "subprocess",
                        "role": "server",
                        "command": [PYTHON, "-m", "tigrcorn", "examples.echo_http.app:app"],
                        "provenance_kind": "package_owned",
                        "implementation_source": "tigrcorn",
                        "implementation_identity": "tigrcorn-http3",
                    },
                    "peer_process": {
                        "name": "tigrcorn-public-client",
                        "adapter": "subprocess",
                        "role": "client",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.external_http3_client"],
                        "provenance_kind": "same_stack_fixture",
                        "implementation_source": "tigrcorn.tests.fixtures_pkg",
                        "implementation_identity": "tigrcorn-public-client",
                    },
                }
            ],
        }
    )
    with pytest.raises(RuntimeError, match="requires a third-party peer"):
        load_external_matrix(matrix_path)


def test_materialize_process_spec_rewrites_hardcoded_pyvenv_python_to_active_interop_python() -> None:
    spec = InteropProcessSpec(
        name="aioquic-wrapper",
        adapter="subprocess",
        role="client",
        command=["/opt/pyvenv/bin/python", "-m", "tests.fixtures_third_party.aioquic_http3_client"],
        version_command=["/opt/pyvenv/bin/python", "-m", "tests.fixtures_third_party.aioquic_http3_client", "--version"],
    )
    prior = os.environ.get("TIGRCORN_INTEROP_PYTHON")
    os.environ["TIGRCORN_INTEROP_PYTHON"] = "/custom/interop/python"
    try:
        resolved = _materialize_process_spec(spec, {})
        assert resolved.command[0] == "/custom/interop/python"
        assert resolved.version_command[0] == "/custom/interop/python"
    finally:
        if prior is None:
            os.environ.pop("TIGRCORN_INTEROP_PYTHON", None)
        else:
            os.environ["TIGRCORN_INTEROP_PYTHON"] = prior


def test_runner_generates_http_evidence_bundle() -> None:
    matrix_path = _write_matrix(
        {
            "name": "http-evidence",
            "scenarios": [
                {
                    "id": "http1-server-fixture-client",
                    "protocol": "http1",
                    "role": "server",
                    "feature": "post-echo",
                    "peer": "fixture-http-client",
                    "sut": {
                        "name": "tigrcorn-http1",
                        "adapter": "subprocess",
                        "role": "server",
                        "command": [PYTHON, "-m", "tigrcorn", "examples.echo_http.app:app", "--host", "{bind_host}", "--port", "{bind_port}", "--protocol", "http1", "--disable-websocket", "--no-access-log", "--lifespan", "off"],
                        "ready_pattern": "listening on",
                        "version_command": [PYTHON, "-m", "tigrcorn", "--help"],
                    },
                    "peer_process": {
                        "name": "fixture-http-client",
                        "adapter": "subprocess",
                        "role": "client",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.interop_http_client"],
                        "version_command": [PYTHON, "-m", "tests.fixtures_pkg.interop_http_client", "--version"],
                    },
                    "assertions": [
                        {"path": "peer.exit_code", "equals": 0},
                        {"path": "transcript.peer.response.status", "equals": 200},
                        {"path": "transcript.peer.response.body", "equals": "echo:hello-interop"},
                        {"path": "artifacts.packet_trace.exists", "equals": True},
                        {"path": "artifacts.packet_trace.size", "greater_or_equal": 1},
                        {"path": "artifacts.peer_transcript.exists", "equals": True},
                    ],
                }
            ],
        }
    )
    with tempfile.TemporaryDirectory() as artifact_root:
        prior = os.environ.get("TIGRCORN_COMMIT_HASH")
        os.environ["TIGRCORN_COMMIT_HASH"] = "deadbeefcafebabe"
        try:
            runner = ExternalInteropRunner(matrix=load_external_matrix(matrix_path), artifact_root=artifact_root, source_root=ROOT)
            summary = runner.run()
            assert summary.total == 1
            assert summary.passed == 1
            result = summary.scenarios[0]
            assert result.passed
            assert result.transcript["peer"]["response"]["body"] == "echo:hello-interop"
            assert result.sut["provenance"]["kind"] == "unspecified"
            assert result.peer["provenance"]["kind"] == "unspecified"
            manifest = json.loads((Path(summary.artifact_root) / "manifest.json").read_text(encoding="utf-8"))
            assert manifest["commit_hash"] == "deadbeefcafebabe"
            assert (Path(result.artifact_dir) / "packet_trace.jsonl").exists()
        finally:
            if prior is None:
                os.environ.pop("TIGRCORN_COMMIT_HASH", None)
            else:
                os.environ["TIGRCORN_COMMIT_HASH"] = prior


def test_runner_generates_quic_qlog_bundle() -> None:
    matrix_path = _write_matrix(
        {
            "name": "quic-observer",
            "scenarios": [
                {
                    "id": "quic-client-fixture-server",
                    "protocol": "quic",
                    "transport": "udp",
                    "role": "client",
                    "feature": "initial-observer-qlog",
                    "peer": "fixture-udp-echo",
                    "sut": {
                        "name": "fixture-quic-client",
                        "adapter": "subprocess",
                        "role": "client",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.interop_quic_client"],
                        "version_command": [PYTHON, "-m", "tests.fixtures_pkg.interop_quic_client", "--version"],
                    },
                    "peer_process": {
                        "name": "fixture-udp-echo",
                        "adapter": "subprocess",
                        "role": "server",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.interop_udp_echo_server"],
                        "ready_pattern": "READY",
                        "version_command": [PYTHON, "-m", "tests.fixtures_pkg.interop_udp_echo_server", "--version"],
                    },
                    "assertions": [
                        {"path": "sut.exit_code", "equals": 0},
                        {"path": "artifacts.packet_trace.exists", "equals": True},
                        {"path": "artifacts.packet_trace.size", "greater_or_equal": 1},
                        {"path": "artifacts.qlog.exists", "equals": True},
                        {"path": "negotiation.sut.alpn", "equals": "h3"},
                    ],
                }
            ],
        }
    )
    with tempfile.TemporaryDirectory() as artifact_root:
        runner = ExternalInteropRunner(matrix=load_external_matrix(matrix_path), artifact_root=artifact_root, source_root=ROOT)
        summary = runner.run()
        assert summary.passed == 1
        result = summary.scenarios[0]
        qlog = json.loads((Path(result.artifact_dir) / "qlog.json").read_text(encoding="utf-8"))
        assert qlog["traces"][0]["vantage_point"]["type"] == "network"
        packet_events = [event for event in qlog["traces"][0]["events"] if event[2].startswith("packet_")]
        assert packet_events
        assert packet_events[0][3]["packets"][0]["packet_type"] == "initial"


def test_failed_assertions_are_recorded() -> None:
    matrix_path = _write_matrix(
        {
            "name": "failure-path",
            "scenarios": [
                {
                    "id": "http1-failure-recording",
                    "protocol": "http1",
                    "role": "server",
                    "feature": "post-echo",
                    "peer": "fixture-http-client",
                    "sut": {
                        "name": "tigrcorn-http1",
                        "adapter": "subprocess",
                        "role": "server",
                        "command": [PYTHON, "-m", "tigrcorn", "examples.echo_http.app:app", "--host", "{bind_host}", "--port", "{bind_port}", "--protocol", "http1", "--disable-websocket", "--no-access-log", "--lifespan", "off"],
                        "ready_pattern": "listening on",
                        "version_command": [PYTHON, "-m", "tigrcorn", "--help"],
                    },
                    "peer_process": {
                        "name": "fixture-http-client",
                        "adapter": "subprocess",
                        "role": "client",
                        "command": [PYTHON, "-m", "tests.fixtures_pkg.interop_http_client"],
                        "version_command": [PYTHON, "-m", "tests.fixtures_pkg.interop_http_client", "--version"],
                    },
                    "assertions": [{"path": "transcript.peer.response.status", "equals": 201}],
                }
            ],
        }
    )
    with tempfile.TemporaryDirectory() as artifact_root:
        runner = ExternalInteropRunner(matrix=load_external_matrix(matrix_path), artifact_root=artifact_root, source_root=ROOT)
        summary = runner.run()
    assert summary.failed == 1
    result = summary.scenarios[0]
    assert not result.passed
    assert result.assertions_failed
    assert "expected 201" in result.assertions_failed[0]


def test_environment_manifest_uses_env_commit_override() -> None:
    prior = os.environ.get("TIGRCORN_COMMIT_HASH")
    os.environ["TIGRCORN_COMMIT_HASH"] = "feedface1234"
    try:
        manifest = build_environment_manifest(ROOT)
    finally:
        if prior is None:
            os.environ.pop("TIGRCORN_COMMIT_HASH", None)
        else:
            os.environ["TIGRCORN_COMMIT_HASH"] = prior
    assert manifest["tigrcorn"]["commit_hash"] == "feedface1234"
    assert "python" in manifest
    assert "tools" in manifest
