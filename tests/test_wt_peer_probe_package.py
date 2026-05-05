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
    assert (PACKAGE_ROOT / "package-lock.json").is_file()
    assert package["name"] == "@tigrcorn/wt-peer-probes"
    assert package["private"] is False
    assert package["files"] == ["dist", "README.md", "examples/browser.html"]
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
    publish = yaml.safe_load((ROOT / ".github" / "workflows" / "publish-wt-peer-probes.yml").read_text(encoding="utf-8"))

    assert "validate-npm" in reusable["jobs"]
    steps = reusable["jobs"]["validate-npm"]["steps"]
    uses = [step.get("uses", "") for step in steps]
    ci_action = next(step for step in steps if step.get("uses") == "cobycloud/actions/actions/setup-node-project@main")
    assert "cobycloud/actions/actions/setup-node-project@main" in uses
    assert ci_action["with"]["working-directory"] == "packages/wt-peer-probes"
    assert ci_action["with"]["install-command"] == "npm ci --workspaces=false"
    assert ci_action["with"]["build-command"] == "npm run build --workspaces=false"
    assert ci_action["with"]["test-command"] == "npm test --workspaces=false"

    assert {"ci", "github-release", "npmjs"} <= set(publish["jobs"])
    release_steps = publish["jobs"]["github-release"]["steps"]
    npm_steps = publish["jobs"]["npmjs"]["steps"]
    release_action = next(step for step in release_steps if step.get("uses") == "cobycloud/actions/actions/github-release@main")
    npm_action = next(step for step in npm_steps if step.get("uses") == "cobycloud/actions/actions/npm-publish@main")
    assert release_action["with"]["files"] == ".artifacts/wt-peer-probes/*.tgz"
    assert npm_action["with"]["package-directory"] == "packages/wt-peer-probes"
    assert npm_action["with"]["scope"] == "@tigrcorn"
    assert npm_action["with"]["install-command"] == "npm ci --workspaces=false"
    assert npm_action["with"]["build-command"] == "npm run build --workspaces=false"
    assert npm_action["with"]["test-command"] == "npm test --workspaces=false"
    assert npm_action["with"]["provenance"] == "true"


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
