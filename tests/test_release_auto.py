from __future__ import annotations

import json
from pathlib import Path

from tools.cert import release_auto
from tools import create_release_promotion_checkpoint as release_promotion

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def _json(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def test_release_auto_artifacts_are_generated_and_aligned():
    release_auto = _json('docs/conformance/release_auto.json')
    evidence_ix = _json('docs/conformance/evidence_ix.json')
    claim_rep = _json('docs/conformance/claim_rep.json')
    risk_stat = _json('docs/conformance/risk_stat.json')
    relnotes = _json('docs/conformance/relnotes.json')

    assert release_auto['authoritative_boundary_passed'] is True
    assert release_auto['strict_target_passed'] is True
    assert release_auto['promotion_target_passed'] is True
    assert evidence_ix['promotion_ready'] is True
    assert claim_rep['implemented_count'] > 0
    assert risk_stat['blocking_open_count'] == 0
    assert Path(relnotes['release_notes']).name.startswith(('RELEASE_NOTES_', 'REL_'))
    assert Path(relnotes['release_notes']).parent.as_posix() == 'docs/release-notes'


def test_publish_all_packages_workflow_uses_tokens_choices_and_pinned_actions():
    workflow = _text('.github/workflows/publish-all-packages.yml')
    assert 'gh_release:' in workflow
    assert 'pypi_publish:' in workflow
    assert 'npmjs_publish:' in workflow
    assert 'package_selection:' in workflow
    assert 'type: choice' in workflow
    assert '- tigrcorn core packages' in workflow
    assert '- probes' in workflow
    assert '- tigrcorn-core' in workflow
    assert '- wt-peer-probes' in workflow
    assert 'environment: testpypi' in workflow
    assert 'environment: pypi' in workflow
    assert 'id-token: write' in workflow
    assert 'user: __token__' not in workflow
    assert 'password: ${{ secrets.PYPI_API_TOKEN }}' not in workflow
    assert 'create-github-tags' in workflow
    assert 'create-github-releases' not in workflow
    assert 'github_releases = plan.get("github_releases", [])' in workflow
    assert 'python_release_tag={python_tag}' in workflow
    assert 'REL_{version}.md' in workflow
    assert 'needs.prepare-release.result == \'success\'' in workflow
    assert 'certification-release-gates' in workflow
    assert 'needs: [release-gates, certification-release-gates]' in workflow
    assert 'Check out prepared release commit' in workflow
    assert 'draft: ${{ github.event_name == \'workflow_dispatch\' && needs.prepare-release.outputs.prerelease == \'true\' }}' in workflow
    assert 'secrets.NPM_API_TOKEN' in workflow
    assert 'uv publish' in workflow
    assert '--trusted-publishing always' in workflow
    assert 'actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26' in workflow
    assert 'softprops/action-gh-release@153bb8e04406b158c6c84fc1615b65b24149a1fe' in workflow
    assert 'actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b' not in workflow
    assert 'npm publish --access public --provenance' in workflow
    assert 'download-artifact' in workflow
    assert '--check-url https://pypi.org/simple/' in workflow
    assert 'python -m build --outdir dist "$package_dir"' in workflow


def test_release_pages_and_docs_pipeline_are_declared():
    workflow = _text('.github/workflows/docs.yml')
    assert 'actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b' not in workflow
    assert 'actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128' not in workflow
    assert 'github-pages' not in workflow
    assert 'name: docs' in workflow
    assert 'Upload docs artifact' in workflow


def test_release_auto_uses_governed_release_notes_naming():
    assert release_auto._release_notes_name('0.3.15') == 'RELEASE_NOTES_0.3.15.md'
    assert release_auto._release_notes_name('0.3.16.dev5') == 'REL_0.3.16.dev5.md'


def test_release_promotion_leaves_newer_dev_versions_unchanged():
    dev_pyproject = '[project]\nname = "tigrcorn"\nversion = "0.3.16.dev5"\n'
    release_pyproject = '[project]\nname = "tigrcorn"\nversion = "0.3.6"\n'

    assert release_promotion.rewrite_root_pyproject_version(dev_pyproject) == dev_pyproject
    assert (
        release_promotion.rewrite_root_pyproject_version(release_pyproject)
        == '[project]\nname = "tigrcorn"\nversion = "0.3.9"\n'
    )
