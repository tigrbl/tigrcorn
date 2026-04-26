from __future__ import annotations

import ast
import importlib
import tomllib
from pathlib import Path

from tools.package_boundaries import PACKAGE_BOUNDARIES, PACKAGE_BY_DISTRIBUTION, workspace_distributions


ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_workspace_declares_all_target_packages() -> None:
    root_pyproject = _load_pyproject(ROOT / "pyproject.toml")
    members = root_pyproject["tool"]["uv"]["workspace"]["members"]

    assert members == ["pkgs/*"]
    for distribution in workspace_distributions():
        package_root = ROOT / "pkgs" / distribution
        assert (package_root / "pyproject.toml").is_file(), distribution
        assert (package_root / "README.md").is_file(), distribution


def test_package_dependency_dag_is_forward_only() -> None:
    for boundary in PACKAGE_BOUNDARIES:
        for dependency in boundary.depends_on:
            if dependency not in PACKAGE_BY_DISTRIBUTION:
                continue
            dependency_boundary = PACKAGE_BY_DISTRIBUTION[dependency]
            assert dependency_boundary.layer < boundary.layer, (boundary.distribution, dependency)


def test_package_pyprojects_match_boundary_manifest() -> None:
    for boundary in PACKAGE_BOUNDARIES:
        pyproject = _load_pyproject(ROOT / "pkgs" / boundary.distribution / "pyproject.toml")
        project = pyproject["project"]
        assert project["name"] == boundary.distribution
        assert project["version"] == "0.3.9"
        declared_dependencies = set(project.get("dependencies", []))
        for dependency in boundary.depends_on:
            if dependency.startswith("tigrcorn-"):
                assert f"{dependency}==0.3.9" in declared_dependencies
            else:
                assert any(item.startswith(dependency) for item in declared_dependencies)
        package_file = ROOT / "pkgs" / boundary.distribution / "src" / boundary.import_name / "__init__.py"
        assert package_file.is_file(), boundary.import_name
        assert (package_file.parent / "py.typed").is_file(), boundary.import_name


def test_extracted_core_is_importable_and_compat_shims_preserve_old_surface() -> None:
    from tigrcorn.constants import H2_PREFACE as shim_preface
    from tigrcorn.errors import ProtocolError as ShimProtocolError
    from tigrcorn.types import Scope as ShimScope
    from tigrcorn_core.constants import H2_PREFACE
    from tigrcorn_core.errors import ProtocolError
    from tigrcorn_core.types import Scope

    assert shim_preface == H2_PREFACE
    assert ShimProtocolError is ProtocolError
    assert ShimScope is Scope


def test_scaffold_import_names_are_available() -> None:
    for boundary in PACKAGE_BOUNDARIES:
        module = importlib.import_module(boundary.import_name)
        assert getattr(module, "PACKAGE_BOUNDARY", "core") in {boundary.distribution.removeprefix("tigrcorn-"), "core"}


def test_split_packages_own_executable_modules_and_root_imports_are_shims() -> None:
    import tigrcorn.asgi.send as root_asgi_send
    import tigrcorn.compat.release_gates as root_release_gates
    import tigrcorn.config.model as root_config_model
    import tigrcorn.contract.events as root_contract_events
    import tigrcorn.flow.keepalive as root_flow_keepalive
    import tigrcorn.http.etag as root_http_etag
    import tigrcorn.observability.metrics as root_observability_metrics
    import tigrcorn.protocols.http1.parser as root_http1_parser
    import tigrcorn.scheduler.runtime as root_scheduler_runtime
    import tigrcorn.security.tls as root_tls
    import tigrcorn.sessions.manager as root_sessions_manager
    import tigrcorn.server.runner as root_server_runner
    import tigrcorn.static as root_static
    import tigrcorn.streams.registry as root_streams_registry
    import tigrcorn.transports.tcp.connection as root_tcp_connection
    import tigrcorn.utils.headers as root_utils_headers
    import tigrcorn.workers.supervisor as root_workers_supervisor
    import tigrcorn_asgi.send as package_asgi_send
    import tigrcorn_certification.release_gates as package_release_gates
    import tigrcorn_config.model as package_config_model
    import tigrcorn_contract.events as package_contract_events
    import tigrcorn_core.utils.headers as package_utils_headers
    import tigrcorn_http.etag as package_http_etag
    import tigrcorn_observability.metrics as package_observability_metrics
    import tigrcorn_protocols.flow.keepalive as package_flow_keepalive
    import tigrcorn_protocols.http1.parser as package_http1_parser
    import tigrcorn_protocols.scheduler.runtime as package_scheduler_runtime
    import tigrcorn_protocols.sessions.manager as package_sessions_manager
    import tigrcorn_protocols.streams.registry as package_streams_registry
    import tigrcorn_runtime.server.runner as package_server_runner
    import tigrcorn_runtime.workers.supervisor as package_workers_supervisor
    import tigrcorn_security.tls as package_tls
    import tigrcorn_static.static as package_static
    import tigrcorn_transports.tcp.connection as package_tcp_connection

    active_pairs = (
        (root_asgi_send.materialize_response_body_segments, package_asgi_send.materialize_response_body_segments, "tigrcorn_asgi"),
        (root_config_model.ServerConfig, package_config_model.ServerConfig, "tigrcorn_config"),
        (root_contract_events.validate_event_order, package_contract_events.validate_event_order, "tigrcorn_contract"),
        (root_flow_keepalive.KeepAlivePolicy, package_flow_keepalive.KeepAlivePolicy, "tigrcorn_protocols"),
        (root_http_etag.generate_entity_tag, package_http_etag.generate_entity_tag, "tigrcorn_http"),
        (root_observability_metrics.Metrics, package_observability_metrics.Metrics, "tigrcorn_observability"),
        (root_http1_parser.ParsedRequestHead, package_http1_parser.ParsedRequestHead, "tigrcorn_protocols"),
        (root_scheduler_runtime.ProductionScheduler, package_scheduler_runtime.ProductionScheduler, "tigrcorn_protocols"),
        (root_tls.ServerTLSContext, package_tls.ServerTLSContext, "tigrcorn_security"),
        (root_sessions_manager.SessionManager, package_sessions_manager.SessionManager, "tigrcorn_protocols"),
        (root_streams_registry.StreamRegistry, package_streams_registry.StreamRegistry, "tigrcorn_protocols"),
        (root_tcp_connection.TCPConnection, package_tcp_connection.TCPConnection, "tigrcorn_transports"),
        (root_utils_headers.get_header, package_utils_headers.get_header, "tigrcorn_core"),
        (root_workers_supervisor.WorkerSupervisor, package_workers_supervisor.WorkerSupervisor, "tigrcorn_runtime"),
        (root_server_runner.TigrCornServer, package_server_runner.TigrCornServer, "tigrcorn_runtime"),
        (root_static.StaticFilesApp, package_static.StaticFilesApp, "tigrcorn_static"),
        (root_release_gates.evaluate_release_gates, package_release_gates.evaluate_release_gates, "tigrcorn_certification"),
    )
    for root_symbol, package_symbol, owner_prefix in active_pairs:
        assert root_symbol is package_symbol
        assert package_symbol.__module__.startswith(owner_prefix)


def test_core_package_has_no_inward_tigrcorn_imports() -> None:
    core_root = ROOT / "pkgs" / "tigrcorn-core" / "src" / "tigrcorn_core"
    forbidden_prefixes = ("tigrcorn.", "tigrcorn_", "tigrcorn-")
    for path in core_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert not name.startswith(forbidden_prefixes), (path, name)


def test_split_packages_do_not_import_legacy_tigrcorn_namespace() -> None:
    for path in (ROOT / "pkgs").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert not name.startswith("tigrcorn."), (path, name)
