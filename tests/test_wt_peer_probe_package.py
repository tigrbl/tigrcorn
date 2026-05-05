from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "packages" / "wt-peer-probes"
PACKAGE_JSON = PACKAGE_ROOT / "package.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_wt_peer_probe_package_is_part_of_npm_workspace() -> None:
    root_package = _json(ROOT / "package.json")
    package = _json(PACKAGE_JSON)

    assert "packages/*" in root_package["workspaces"]
    assert package["name"] == "@tigrcorn/wt-peer-probes"
    assert package["private"] is False
    assert package["exports"]["."]["import"] == "./dist/index.js"
    assert package["exports"]["."]["types"] == "./dist/index.d.ts"


def test_wt_peer_probe_package_exports_browser_probe_contract() -> None:
    source = (PACKAGE_ROOT / "src" / "probe.ts").read_text(encoding="utf-8")
    types = (PACKAGE_ROOT / "src" / "types.ts").read_text(encoding="utf-8")
    index = (PACKAGE_ROOT / "src" / "index.ts").read_text(encoding="utf-8")

    assert 'probe: "tigrcorn.wt.peer"' in source
    assert "new WebTransport(opts.wtUrl)" in source
    for stage in ("api", "ready", "bidi", "unidi", "datagram", "close"):
        assert f"{stage}:" in source or f"{stage}:" in types
    assert "runTigrcornWTPeerProbe" in index


def test_wt_peer_probe_playwright_matrix_is_peer_based() -> None:
    config = (PACKAGE_ROOT / "playwright.config.ts").read_text(encoding="utf-8")
    spec = (PACKAGE_ROOT / "tests" / "wt-peer-probe.playwright.spec.ts").read_text(encoding="utf-8")

    for project in ("chromium", "firefox", "webkit", "mobile-chrome", "mobile-safari"):
        assert f'name: "{project}"' in config
    assert "TIGRCORN_WT_URL" in spec
    assert "TIGRCORN_WT_REPORT_URL" in spec
    assert "testInfo.project.name" in spec


def test_wt_peer_probe_package_has_ci_and_publish_rails() -> None:
    reusable = yaml.safe_load((ROOT / ".github" / "workflows" / "_reusable-ci.yml").read_text(encoding="utf-8"))
    publish = yaml.safe_load((ROOT / ".github" / "workflows" / "publish-npm.yml").read_text(encoding="utf-8"))

    assert "validate-npm" in reusable["jobs"]
    steps = reusable["jobs"]["validate-npm"]["steps"]
    commands = [step.get("run", "") for step in steps]
    assert "npm install" in commands
    assert "npm run typecheck" in commands
    assert "npm run build" in commands
    assert "npm test" in commands

    publish_steps = publish["jobs"]["publish-npm"]["steps"]
    publish_commands = [step.get("run", "") for step in publish_steps]
    assert "npm publish --workspace packages/wt-peer-probes --access public --provenance" in publish_commands


def test_wt_peer_probe_contract_is_registered_in_ssot() -> None:
    registry = _json(ROOT / ".ssot" / "registry.json")
    features = {row["id"]: row for row in registry["features"]}
    tests = {row["id"]: row for row in registry["tests"]}

    feature = features["feat:webtransport-peer-probe-npm-package"]
    test = tests["tst:webtransport-peer-probe-npm-package"]

    assert feature["implementation_status"] == "implemented"
    assert feature["plan"]["horizon"] == "current"
    assert feature["plan"]["slot"] == "webtransport-peer-probes"
    assert "spc:2010" in feature["spec_ids"]
    assert test["path"] == "tests/test_wt_peer_probe_package.py"
    assert feature["id"] in test["feature_ids"]
