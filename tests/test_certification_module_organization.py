from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CERTIFICATION_PATH = (
    ROOT
    / "pkgs"
    / "tigrcorn-certification"
    / "src"
    / "tigrcorn_certification"
)
INTEROP_PATH = CERTIFICATION_PATH / "interop_runner"
RELEASE_GATES_PATH = CERTIFICATION_PATH / "release_gates"


def _package_source(path: Path) -> str:
    return "\n".join(file.read_text(encoding="utf-8") for file in sorted(path.glob("*.py")))


def test_certification_python_files_stay_under_400_loc() -> None:
    oversized = []
    for path in sorted(CERTIFICATION_PATH.rglob("*.py")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 400:
            oversized.append((path.relative_to(ROOT).as_posix(), line_count))

    assert oversized == []


def test_certification_public_imports_remain_compatible() -> None:
    from tigrcorn_certification import certify_static
    from tigrcorn_certification import evaluate_release_gates as RootReleaseGates
    from tigrcorn_certification import export_hardening_suite_catalog
    from tigrcorn_certification.aioquic_preflight import run_aioquic_adapter_preflight
    from tigrcorn_certification.interop_runner import run_external_matrix
    from tigrcorn_certification.perf_runner import run_performance_matrix
    from tigrcorn_certification.release_gates import evaluate_release_gates

    assert RootReleaseGates is evaluate_release_gates
    assert callable(run_external_matrix)
    assert callable(run_performance_matrix)
    assert callable(run_aioquic_adapter_preflight)
    assert callable(certify_static)
    assert callable(export_hardening_suite_catalog)


def test_interop_transport_harness_code_is_isolated() -> None:
    proxies_source = (INTEROP_PATH / "proxies.py").read_text(encoding="utf-8")
    ports_source = (INTEROP_PATH / "ports.py").read_text(encoding="utf-8")
    other_source = "\n".join(
        file.read_text(encoding="utf-8")
        for file in sorted(INTEROP_PATH.glob("*.py"))
        if file.name not in {"proxies.py", "ports.py"}
    )

    assert "class TCPRecordProxy" in proxies_source
    assert "class UDPRecordProxy" in proxies_source
    assert "class _TCPRelay" in proxies_source
    assert "def _reserve_port(" in ports_source
    assert "def _probe_server_port(" in ports_source
    assert "class TCPRecordProxy" not in other_source
    assert "class UDPRecordProxy" not in other_source


def test_interop_protocol_observation_code_is_isolated() -> None:
    qlog_source = (INTEROP_PATH / "qlog.py").read_text(encoding="utf-8")
    other_source = "\n".join(
        file.read_text(encoding="utf-8")
        for file in sorted(INTEROP_PATH.glob("*.py"))
        if file.name != "qlog.py"
    )

    assert "def generate_observer_qlog(" in qlog_source
    assert "def _describe_quic_packet(" in qlog_source
    assert "def _redact_qlog_packet(" in qlog_source
    assert "def _describe_quic_packet(" not in other_source


def test_release_gates_do_not_import_runtime_protocol_or_transport_packages() -> None:
    source = _package_source(RELEASE_GATES_PATH)

    forbidden = (
        "tigrcorn_protocols.",
        "tigrcorn_transports.",
        "tigrcorn_runtime.",
    )
    for token in forbidden:
        assert token not in source


def test_certify_command_modules_do_not_import_runtime_protocol_transport_or_security() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            CERTIFICATION_PATH / "certify" / "__init__.py",
            CERTIFICATION_PATH / "certify" / "static.py",
            CERTIFICATION_PATH / "hardening_suites.py",
        ]
    )

    forbidden = (
        "tigrcorn_runtime.",
        "tigrcorn_protocols.",
        "tigrcorn_transports.",
        "tigrcorn_security.",
    )
    for token in forbidden:
        assert token not in source
