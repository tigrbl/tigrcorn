from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tigrcorn.compat.certification_env import (
    CertificationEnvironmentError,
    build_certification_environment_snapshot,
    write_certification_environment_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.8' / 'release-0.3.8'
BUNDLE_ROOT = RELEASE_ROOT / 'tigrcorn-certification-environment-bundle'


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_certification_environment_docs_bundle_and_workflow_exist() -> None:
    assert (CONFORMANCE / 'CERTIFICATION_ENVIRONMENT_FREEZE.md').exists()
    assert (CONFORMANCE / 'certification_environment_freeze.current.json').exists()
    assert (ROOT / 'DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md').exists()
    assert BUNDLE_ROOT.exists()
    assert (ROOT / '.github' / 'workflows' / 'phase9-certification-release.yml').exists()
    assert (ROOT / 'tools' / 'run_phase9_release_workflow.py').exists()

    manifest = _load_json(RELEASE_ROOT / 'manifest.json')
    assert 'certification_environment' in manifest['bundles']
    assert manifest['bundles']['certification_environment']['path'] == str(BUNDLE_ROOT.relative_to(ROOT))

    bundle_index = _load_json(BUNDLE_ROOT / 'index.json')
    status = _load_json(CONFORMANCE / 'certification_environment_freeze.current.json')
    assert bundle_index['artifact_root'] == status['current_state']['bundle_root']
    assert bundle_index['workflow_path'] == status['current_state']['workflow_path']
    assert bundle_index['wrapper_path'] == status['current_state']['wrapper_path']
    assert bundle_index['required_imports_ready'] == status['current_state']['required_imports_ready']
    assert bundle_index['python_version_ready'] == status['current_state']['python_version_ready']


def test_certification_environment_snapshot_builder_records_contract() -> None:
    snapshot = build_certification_environment_snapshot(ROOT)
    assert snapshot['installation_contract']['install_command'] == 'python -m pip install -e ".[certification,dev]"'
    assert snapshot['installation_contract']['required_extras'] == ['certification', 'dev']
    assert snapshot['validation']['required_imports'] == ['aioquic', 'h2', 'websockets', 'wsproto']
    assert snapshot['release_workflow']['workflow_path'] == '.github/workflows/phase9-certification-release.yml'
    assert snapshot['release_workflow']['wrapper_path'] == 'tools/run_phase9_release_workflow.py'


def test_certification_environment_bundle_writer_supports_non_ready_environments() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / 'bundle'
        snapshot = write_certification_environment_bundle(
            ROOT,
            bundle_root=target,
            workflow_path='.github/workflows/phase9-certification-release.yml',
            wrapper_path='tools/run_phase9_release_workflow.py',
            require_ready=False,
        )
        assert (target / 'environment.json').exists()
        assert (target / 'manifest.json').exists()
        assert (target / 'index.json').exists()
        assert (target / 'summary.json').exists()
        assert (target / 'bootstrap.sh').exists()
        index = _load_json(target / 'index.json')
        assert index['artifact_root'].endswith('bundle')
        assert index['required_imports_ready'] == snapshot['validation']['required_imports_ready']
        assert index['python_version_ready'] == snapshot['validation']['python_version_ready']


def test_certification_environment_bundle_writer_strict_mode_tracks_readiness() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / 'bundle'
        snapshot = build_certification_environment_snapshot(ROOT)
        if snapshot['validation']['environment_ready_for_release_workflow']:
            write_certification_environment_bundle(ROOT, bundle_root=target, require_ready=True)
            assert (target / 'environment.json').exists()
        else:
            with pytest.raises(CertificationEnvironmentError):
                write_certification_environment_bundle(ROOT, bundle_root=target, require_ready=True)


def test_release_workflow_and_wrapper_enforce_freeze_before_phase9_scripts() -> None:
    workflow = (ROOT / '.github' / 'workflows' / 'phase9-certification-release.yml').read_text(encoding='utf-8')
    wrapper = (ROOT / 'tools' / 'run_phase9_release_workflow.py').read_text(encoding='utf-8')
    assert 'pip install -e ".[certification,dev]"' in workflow
    assert 'tools/freeze_certification_environment.py' in workflow
    assert '--require-imports' in workflow
    assert 'freeze_certification_environment.py' in wrapper
    assert '--require-imports' in wrapper
    assert 'tools/create_phase9i_release_assembly_checkpoint.py' in wrapper
