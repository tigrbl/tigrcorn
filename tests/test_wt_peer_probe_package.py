from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "packages" / "wt-peer-probes"
PACKAGE_JSON = PACKAGE_ROOT / "package.json"
BROWSER_PEERS = {
    "chromium": "Chromium",
    "firefox": "Firefox",
    "webkit": "WebKit/Safari",
    "mobile-chrome": "Mobile Chrome",
    "mobile-safari": "Mobile Safari",
}


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
    assert package["scripts"]["test:peer-api"] == "playwright test tests/wt-peer-api-protocol.playwright.spec.ts"


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
    peer_api_spec = (PACKAGE_ROOT / "tests" / "wt-peer-api-protocol.playwright.spec.ts").read_text(encoding="utf-8")

    for project in BROWSER_PEERS:
        assert f'name: "{project}"' in config
    assert "TIGRCORN_WT_URL" in spec
    assert "TIGRCORN_WT_REPORT_URL" in spec
    assert "TIGRCORN_WT_LIVE" in spec
    assert "testInfo.project.name" in spec
    assert "FakeWebTransport" in peer_api_spec
    assert 'type: "probe.bidi.echo.ok"' in peer_api_spec
    assert 'type: "probe.unidi.ack"' in peer_api_spec
    assert 'type: "probe.datagram.echo.ok"' in peer_api_spec
    assert "runTigrcornWTPeerProbe" in (PACKAGE_ROOT / "examples" / "browser.html").read_text(encoding="utf-8")


def test_wt_peer_probe_package_has_ci_and_publish_rails() -> None:
    reusable = yaml.safe_load((ROOT / ".github" / "workflows" / "_reusable-ci.yml").read_text(encoding="utf-8"))
    publish = yaml.safe_load((ROOT / ".github" / "workflows" / "publish-all-packages.yml").read_text(encoding="utf-8"))

    assert "validate-npm" in reusable["jobs"]
    assert "validate-wt-peer-probes" in reusable["jobs"]
    steps = reusable["jobs"]["validate-npm"]["steps"]
    peer_steps = reusable["jobs"]["validate-wt-peer-probes"]["steps"]
    ci_action = next(step for step in steps if step.get("uses") == "cobycloud/actions/actions/setup-node-project@main")
    peer_action = next(step for step in peer_steps if step.get("uses") == "cobycloud/actions/actions/playwright-ci@main")
    assert ci_action["with"]["working-directory"] == "packages/wt-peer-probes"
    assert ci_action["with"]["install-command"] == "npm ci --workspaces=false"
    assert ci_action["with"]["build-command"] == "npm run build --workspaces=false"
    assert ci_action["with"]["test-command"] == "npm test --workspaces=false"
    assert peer_action["with"]["working-directory"] == "packages/wt-peer-probes"
    assert peer_action["with"]["browser-install-command"] == "npx playwright install --with-deps chromium firefox webkit"
    assert peer_action["with"]["test-command"] == "npm run test:peer-api -- --reporter=line"

    triggers = publish.get("on") or publish.get(True)
    workflow_dispatch = triggers["workflow_dispatch"]["inputs"]
    assert {"gh_release", "pypi_publish", "npmjs_publish", "package_selection"} <= set(workflow_dispatch)
    assert {"all", "tigrcorn core packages", "probes", "wt-peer-probes"} <= set(workflow_dispatch["package_selection"]["options"])

    assert {
        "wt-peer-probes-ci",
        "wt-peer-probes-browser-tests",
        "publish-wt-peer-probes-github-release",
        "publish-wt-peer-probes-npmjs",
    } <= set(publish["jobs"])
    publish_peer_steps = publish["jobs"]["wt-peer-probes-browser-tests"]["steps"]
    release_steps = publish["jobs"]["publish-wt-peer-probes-github-release"]["steps"]
    npm_steps = publish["jobs"]["publish-wt-peer-probes-npmjs"]["steps"]
    publish_peer_action = next(step for step in publish_peer_steps if step.get("uses") == "cobycloud/actions/actions/playwright-ci@main")
    release_action = next(step for step in release_steps if step.get("uses") == "cobycloud/actions/actions/github-release@main")
    npm_action = next(step for step in npm_steps if step.get("uses") == "cobycloud/actions/actions/npm-publish@main")
    assert publish["jobs"]["publish-wt-peer-probes-github-release"]["needs"] == [
        "wt-peer-probes-ci",
        "wt-peer-probes-browser-tests",
    ]
    assert publish["jobs"]["publish-wt-peer-probes-npmjs"]["needs"] == [
        "wt-peer-probes-ci",
        "wt-peer-probes-browser-tests",
    ]
    assert publish_peer_action["with"]["test-command"] == "npm run test:peer-api -- --reporter=line"
    assert release_action["with"]["files"] == ".artifacts/wt-peer-probes/*.tgz"
    assert npm_action["with"]["package-directory"] == "packages/wt-peer-probes"
    assert npm_action["with"]["scope"] == "@tigrcorn"
    assert npm_action["with"]["npm-token"] == "${{ secrets.NPM_API_TOKEN }}"
    assert npm_action["with"]["install-command"] == "npm ci --workspaces=false"
    assert npm_action["with"]["build-command"] == "npm run build --workspaces=false"
    assert npm_action["with"]["test-command"] == "npm test --workspaces=false"
    assert npm_action["with"]["provenance"] == "true"


def test_wt_peer_probe_contract_is_registered_in_ssot() -> None:
    registry = _json(ROOT / ".ssot" / "registry.json")
    features = {row["id"]: row for row in registry["features"]}
    tests = {row["id"]: row for row in registry["tests"]}

    umbrella = features["feat:webtransport-peer-apis"]
    umbrella_test = tests["tst:webtransport-peer-apis"]
    feature = features["feat:webtransport-peer-probe-npm-package"]
    test = tests["tst:webtransport-peer-probe-npm-package"]

    assert umbrella["implementation_status"] == "implemented"
    assert umbrella["plan"]["horizon"] == "current"
    assert umbrella["plan"]["slot"] == "webtransport-peer-probes"
    assert umbrella["plan"]["target_claim_tier"] == "T3"
    assert umbrella_test["kind"] == "playwright"
    assert umbrella_test["path"] == "packages/wt-peer-probes/tests/wt-peer-api-protocol.playwright.spec.ts"
    assert umbrella["id"] in umbrella_test["feature_ids"]

    assert feature["implementation_status"] == "implemented"
    assert feature["plan"]["horizon"] == "current"
    assert feature["plan"]["slot"] == "webtransport-peer-probes"
    assert "spc:2010" in feature["spec_ids"]
    assert umbrella["id"] in feature["requires"]
    assert test["path"] == "tests/test_wt_peer_probe_package.py"
    assert feature["id"] in test["feature_ids"]

    package_feature_id = "feat:webtransport-peer-probe-npm-package"
    umbrella_feature_id = "feat:webtransport-peer-apis"
    for browser_id in BROWSER_PEERS:
        feature_id = f"feat:webtransport-peer-probe-{browser_id}"
        test_id = f"tst:webtransport-peer-probe-{browser_id}"
        browser_feature = features[feature_id]
        browser_test = tests[test_id]

        assert browser_feature["implementation_status"] == "implemented"
        assert browser_feature["plan"]["horizon"] == "current"
        assert browser_feature["plan"]["slot"] == "webtransport-peer-probes"
        assert browser_feature["plan"]["target_claim_tier"] == "T3"
        assert umbrella_feature_id in browser_feature["requires"]
        assert package_feature_id in browser_feature["requires"]
        assert browser_test["kind"] == "playwright"
        assert browser_test["path"] == "packages/wt-peer-probes/tests/wt-peer-api-protocol.playwright.spec.ts"
        assert feature_id in browser_test["feature_ids"]
