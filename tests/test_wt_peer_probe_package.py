from __future__ import annotations

import json
from pathlib import Path

import yaml
from tigrcorn.ssot_baseline import iter_feature_baselines


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


def _has_t012_baseline(registry: dict, feature_id: str) -> bool:
    baselines = {baseline.feature_id: baseline for baseline in iter_feature_baselines(registry)}
    return set(baselines[feature_id].claim_tiers) >= {"T0", "T1", "T2"}


def test_wt_peer_probe_package_is_part_of_npm_workspace() -> None:
    root_package = _json(ROOT / "package.json")
    package = _json(PACKAGE_JSON)

    assert "packages/*" in root_package["workspaces"]
    assert (PACKAGE_ROOT / "package-lock.json").is_file()
    assert package["name"] == "@tigrcorn/wt-peer-probes"
    assert package["private"] is False
    assert package["repository"]["url"] == "https://github.com/tigrbl/tigrcorn"
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
    reusable_text = (ROOT / ".github" / "workflows" / "_reusable-ci.yml").read_text(encoding="utf-8")
    reusable = yaml.safe_load(reusable_text)
    publish = yaml.safe_load((ROOT / ".github" / "workflows" / "publish-all-packages.yml").read_text(encoding="utf-8"))

    assert "validate-npm" in reusable["jobs"]
    assert "validate-wt-peer-probes" in reusable["jobs"]
    steps = reusable["jobs"]["validate-npm"]["steps"]
    peer_steps = reusable["jobs"]["validate-wt-peer-probes"]["steps"]
    assert any(step.get("uses") == "actions/setup-node@v4" for step in steps)
    assert any(step.get("uses") == "actions/setup-node@v4" for step in peer_steps)
    assert any(
        step.get("working-directory") == "packages/wt-peer-probes" and step.get("run") == "npm ci --workspaces=false"
        for step in steps
    )
    assert any(
        step.get("working-directory") == "packages/wt-peer-probes" and step.get("run") == "npm run build --workspaces=false"
        for step in steps
    )
    assert any(
        step.get("working-directory") == "packages/wt-peer-probes" and step.get("run") == "npm test --workspaces=false"
        for step in steps
    )
    assert "timeout 90m npx playwright install --with-deps chromium firefox webkit" in reusable_text
    assert any(
        step.get("working-directory") == "packages/wt-peer-probes"
        and step.get("run") == "npm run test:peer-api -- --reporter=line"
        for step in peer_steps
    )

    triggers = publish.get("on") or publish.get(True)
    workflow_dispatch = triggers["workflow_dispatch"]["inputs"]
    assert {"gh_release", "pypi_publish", "npmjs_publish", "package_selection"} <= set(workflow_dispatch)
    assert {"all", "tigrcorn core packages", "probes", "wt-peer-probes"} <= set(workflow_dispatch["package_selection"]["options"])
    assert "certification-release-gates" in publish["jobs"]
    assert publish["jobs"]["prepare-release"]["needs"] == ["release-gates", "certification-release-gates"]

    assert {
        "wt-peer-probes-ci",
        "wt-peer-probes-browser-tests",
        "publish-wt-peer-probes-github-release",
        "publish-wt-peer-probes-npmjs",
    } <= set(publish["jobs"])
    publish_peer_steps = publish["jobs"]["wt-peer-probes-browser-tests"]["steps"]
    release_steps = publish["jobs"]["publish-wt-peer-probes-github-release"]["steps"]
    npm_steps = publish["jobs"]["publish-wt-peer-probes-npmjs"]["steps"]
    release_action = next(step for step in release_steps if step.get("uses") == "cobycloud/actions/actions/github-release@main")
    assert publish["jobs"]["publish-wt-peer-probes-github-release"]["needs"] == [
        "prepare-release",
        "create-github-tags",
        "wt-peer-probes-ci",
        "wt-peer-probes-browser-tests",
    ]
    assert publish["jobs"]["publish-wt-peer-probes-npmjs"]["needs"] == [
        "prepare-release",
        "wt-peer-probes-ci",
        "wt-peer-probes-browser-tests",
    ]
    assert any(
        step.get("working-directory") == "packages/wt-peer-probes"
        and step.get("run") == "npm run test:peer-api -- --reporter=line"
        for step in publish_peer_steps
    )
    assert release_action["with"]["files"] == ".artifacts/wt-peer-probes/*.tgz"
    publish_step = next(step for step in npm_steps if step.get("uses") == "cobycloud/actions/actions/npm-publish@main" and step["with"].get("dry-run") != "true")
    assert publish_step["with"]["publish-mode"] == "trusted"
    assert publish_step["with"]["node-version"] == "25"
    assert publish_step["with"]["package-directory"] == "packages/wt-peer-probes"
    assert publish_step["with"]["install-command"] == "npm ci --workspaces=false"
    assert publish_step["with"]["build-command"] == "npm run build --workspaces=false"
    assert publish_step["with"]["test-command"] == "npm test --workspaces=false"
    assert publish_step["with"]["provenance"] == "true"


def test_wt_peer_probe_contract_is_registered_in_ssot() -> None:
    registry = _json(ROOT / ".ssot" / "registry.json")
    features = {row["id"]: row for row in registry["features"]}
    tests = {row["id"]: row for row in registry["tests"]}

    umbrella = features["feat:webtransport-peer-apis"]
    umbrella_test = tests["tst:webtransport-peer-apis"]
    feature = features["feat:webtransport-peer-probe-npm-package"]
    test = tests["tst:webtransport-peer-probe-npm-package"]

    assert _has_t012_baseline(registry, umbrella["id"])
    assert umbrella["plan"]["horizon"] == "current"
    assert umbrella["plan"]["slot"] == "webtransport-peer-probes"
    assert umbrella["plan"]["target_claim_tier"] == "T2"
    assert umbrella_test["kind"] == "playwright"
    assert umbrella_test["path"] == "packages/wt-peer-probes/tests/wt-peer-api-protocol.playwright.spec.ts"
    assert umbrella["id"] in umbrella_test["feature_ids"]

    assert _has_t012_baseline(registry, feature["id"])
    assert feature["plan"]["horizon"] == "current"
    assert feature["plan"]["slot"] == "webtransport-peer-probes"
    assert "spc:2010" in feature["spec_ids"]
    assert umbrella["id"] in feature.get("requires", []) or _has_t012_baseline(registry, feature["id"])
    assert test["path"] == "tests/test_wt_peer_probe_package.py"
    assert feature["id"] in test["feature_ids"]

    package_feature_id = "feat:webtransport-peer-probe-npm-package"
    umbrella_feature_id = "feat:webtransport-peer-apis"
    for browser_id in BROWSER_PEERS:
        feature_id = f"feat:webtransport-peer-probe-{browser_id}"
        test_id = f"tst:webtransport-peer-probe-{browser_id}"
        browser_feature = features[feature_id]
        browser_test = tests[test_id]

        assert _has_t012_baseline(registry, feature_id)
        assert browser_feature["plan"]["horizon"] == "current"
        assert browser_feature["plan"]["slot"] == "webtransport-peer-probes"
        assert browser_feature["plan"]["target_claim_tier"] == "T2"
        assert umbrella_feature_id in browser_feature.get("requires", []) or _has_t012_baseline(registry, feature_id)
        assert package_feature_id in browser_feature.get("requires", []) or _has_t012_baseline(registry, feature_id)
        assert browser_test["kind"] == "playwright"
        assert browser_test["path"] == "packages/wt-peer-probes/tests/wt-peer-api-protocol.playwright.spec.ts"
        assert feature_id in browser_test["feature_ids"]
