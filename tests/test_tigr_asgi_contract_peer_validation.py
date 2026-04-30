from __future__ import annotations

from importlib import metadata as importlib_metadata
from pathlib import Path
import tomllib

import tigr_asgi_contract as contract

from tests.contract_closure_assertions import ContractClosureAssertions
from tools.package_boundaries import PACKAGE_BY_DISTRIBUTION


ROOT = Path(__file__).resolve().parents[1]


def _project_dependencies(path: Path) -> set[str]:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    return set(project.get("dependencies", []))


def test_tigr_asgi_contract_is_external_peer_dependency() -> None:
    boundary = PACKAGE_BY_DISTRIBUTION["tigrcorn-contract"]
    contract_dependencies = _project_dependencies(ROOT / "pkgs" / "tigrcorn-contract" / "pyproject.toml")
    umbrella_dependencies = _project_dependencies(ROOT / "pyproject.toml")

    assert "tigr-asgi-contract" in boundary.depends_on
    assert "tigr-asgi-contract" not in PACKAGE_BY_DISTRIBUTION
    assert any(dependency.startswith("tigr-asgi-contract>=") for dependency in contract_dependencies)
    assert "tigrcorn-contract==0.3.9" in umbrella_dependencies
    assert any(dependency.startswith("tigr-asgi-contract>=") for dependency in umbrella_dependencies)


def test_tigr_asgi_contract_peer_version_matches_installed_surface() -> None:
    assert importlib_metadata.version("tigr-asgi-contract") == contract.CONTRACT_VERSION


class TigrASGIContractPeerValidationTests(ContractClosureAssertions):
    def test_tigr_asgi_contract_peer_surface(self) -> None:
        self.assert_contract_validation_surface()
