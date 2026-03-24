from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SUPPORTED_PYTHON_VERSIONS: tuple[str, ...] = ('3.11', '3.12')
REQUIRED_IMPORTS: tuple[str, ...] = ('aioquic', 'h2', 'websockets', 'wsproto')
REQUIRED_EXTRAS: tuple[str, ...] = ('certification', 'dev')
SAFE_ENV_KEYS: tuple[str, ...] = (
    'PYTHONPATH',
    'VIRTUAL_ENV',
    'PIP_CONSTRAINT',
    'PIP_REQUIRE_VIRTUALENV',
)
DEFAULT_BUNDLE_NAME = 'tigrcorn-certification-environment-bundle'
DEFAULT_STATUS_DOC = 'docs/review/conformance/CERTIFICATION_ENVIRONMENT_FREEZE.md'
DEFAULT_STATUS_JSON = 'docs/review/conformance/certification_environment_freeze.current.json'
DEFAULT_DELIVERY_NOTES = 'DELIVERY_NOTES_CERTIFICATION_ENVIRONMENT_FREEZE.md'
DEFAULT_RELEASE_WORKFLOW = '.github/workflows/phase9-certification-release.yml'
DEFAULT_WRAPPER = 'tools/run_phase9_release_workflow.py'
DEFAULT_INSTALL_COMMAND = 'python -m pip install -e ".[certification,dev]"'
DEFAULT_VERIFY_COMMAND = "python - <<'PY'\nimport aioquic, h2, websockets, wsproto\nprint('certification deps OK')\nPY"


class CertificationEnvironmentError(RuntimeError):
    """Raised when the release certification environment contract is not satisfied."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_pyproject(root: Path) -> dict[str, Any]:
    return tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))


def _load_optional_dependencies(root: Path) -> dict[str, list[str]]:
    payload = _read_pyproject(root)
    project = payload.get('project', {})
    optional = project.get('optional-dependencies', {})
    return {str(name): [str(item) for item in values] for name, values in optional.items()}


def _safe_env_snapshot(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if env is None else env
    return {key: str(source[key]) for key in SAFE_ENV_KEYS if key in source}


def _module_status(module_name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(module_name)
    importable = spec is not None
    try:
        version = importlib.metadata.version(module_name)
        installed = True
    except importlib.metadata.PackageNotFoundError:
        version = None
        installed = False
    return {
        'module': module_name,
        'importable': importable,
        'installed': installed,
        'version': version,
    }


def _current_python_version() -> str:
    return f'{sys.version_info.major}.{sys.version_info.minor}'


def _python_ready() -> bool:
    return _current_python_version() in SUPPORTED_PYTHON_VERSIONS


def _capture_command(command: Sequence[str] | None) -> list[str]:
    if command is None:
        return [sys.executable, *sys.argv]
    return [str(item) for item in command]


def _resolve_git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def build_certification_environment_snapshot(
    root: str | Path,
    *,
    command: Sequence[str] | None = None,
    workflow_path: str = DEFAULT_RELEASE_WORKFLOW,
    wrapper_path: str = DEFAULT_WRAPPER,
) -> dict[str, Any]:
    repo_root = Path(root)
    optional = _load_optional_dependencies(repo_root)
    current_python = _current_python_version()
    dependency_state = {name: _module_status(name) for name in REQUIRED_IMPORTS}
    missing_imports = [name for name, state in dependency_state.items() if not state['importable']]
    required_imports_ready = not missing_imports
    python_version_ready = current_python in SUPPORTED_PYTHON_VERSIONS

    extras = {
        name: optional.get(name, []) for name in REQUIRED_EXTRAS
    }
    frozen_dependencies = {
        name: {
            **dependency_state[name],
            'declared_in_extras': [extra for extra, requirements in extras.items() if any(requirement.split('>=', 1)[0].split('==', 1)[0] == name for requirement in requirements)],
        }
        for name in REQUIRED_IMPORTS
    }

    snapshot: dict[str, Any] = {
        'schema_version': 1,
        'captured_at': _now(),
        'repository_root': '.',
        'git_commit': _resolve_git_commit(repo_root),
        'python': {
            'executable': sys.executable,
            'version': sys.version,
            'minor_version': current_python,
            'supported_release_workflow_versions': list(SUPPORTED_PYTHON_VERSIONS),
            'version_ready': python_version_ready,
            'implementation': platform.python_implementation(),
            'platform': platform.platform(),
            'machine': platform.machine(),
        },
        'installation_contract': {
            'required_extras': list(REQUIRED_EXTRAS),
            'optional_dependencies': extras,
            'install_command': DEFAULT_INSTALL_COMMAND,
            'verify_command': DEFAULT_VERIFY_COMMAND,
            'bootstrap_commands': [
                'python -m venv .venv',
                'source .venv/bin/activate',
                'python -m pip install -U pip',
                DEFAULT_INSTALL_COMMAND,
                DEFAULT_VERIFY_COMMAND,
            ],
        },
        'dependencies': frozen_dependencies,
        'environment': {
            'selected_variables': _safe_env_snapshot(),
            'command': _capture_command(command),
        },
        'release_workflow': {
            'workflow_path': workflow_path,
            'wrapper_path': wrapper_path,
        },
        'validation': {
            'required_imports': list(REQUIRED_IMPORTS),
            'required_imports_ready': required_imports_ready,
            'missing_imports': missing_imports,
            'python_version_ready': python_version_ready,
            'environment_ready_for_release_workflow': python_version_ready and required_imports_ready,
        },
    }
    return snapshot


def _bundle_manifest(bundle_root: Path, artifact_root: str, snapshot: Mapping[str, Any], *, workflow_path: str, wrapper_path: str) -> dict[str, Any]:
    return {
        'bundle_kind': 'certification_environment_bundle',
        'generated_at': snapshot['captured_at'],
        'release_gate_eligible': False,
        'artifact_root': artifact_root,
        'install_command': snapshot['installation_contract']['install_command'],
        'verify_command': snapshot['installation_contract']['verify_command'],
        'workflow_path': workflow_path,
        'wrapper_path': wrapper_path,
        'note': 'This bundle freezes the certification-environment installation contract and the observed execution environment for the strict-promotion workflow.',
    }


def _bundle_index(bundle_root: Path, artifact_root: str, snapshot: Mapping[str, Any], *, workflow_path: str, wrapper_path: str, environment_file: str) -> dict[str, Any]:
    validation = dict(snapshot['validation'])
    return {
        'artifact_root': artifact_root,
        'bundle_kind': 'certification_environment_bundle',
        'generated_at': snapshot['captured_at'],
        'status': 'certification_environment_ready' if validation['environment_ready_for_release_workflow'] else 'certification_environment_frozen_but_not_ready',
        'required_extras': list(snapshot['installation_contract']['required_extras']),
        'required_imports': list(validation['required_imports']),
        'required_imports_ready': validation['required_imports_ready'],
        'missing_imports': list(validation['missing_imports']),
        'python_minor_version': snapshot['python']['minor_version'],
        'python_version_ready': validation['python_version_ready'],
        'environment_ready_for_release_workflow': validation['environment_ready_for_release_workflow'],
        'install_command': snapshot['installation_contract']['install_command'],
        'verify_command': snapshot['installation_contract']['verify_command'],
        'environment_snapshot': environment_file,
        'workflow_path': workflow_path,
        'wrapper_path': wrapper_path,
    }


def _bundle_summary(index: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'bundle_kind': index['bundle_kind'],
        'generated_at': index['generated_at'],
        'status': index['status'],
        'python_minor_version': index['python_minor_version'],
        'python_version_ready': index['python_version_ready'],
        'required_imports_ready': index['required_imports_ready'],
        'missing_imports': index['missing_imports'],
    }


def _bundle_readme(snapshot: Mapping[str, Any], *, workflow_path: str, wrapper_path: str) -> str:
    validation = snapshot['validation']
    missing_imports = ', '.join(validation['missing_imports']) if validation['missing_imports'] else 'none'
    return (
        '# Certification environment bundle\n\n'
        'This bundle freezes the release-workflow installation contract for the strict-promotion certification path.\n\n'
        'Required bootstrap commands:\n\n'
        '```bash\n'
        'python -m venv .venv\n'
        'source .venv/bin/activate\n'
        'python -m pip install -U pip\n'
        f"{snapshot['installation_contract']['install_command']}\n"
        f"{snapshot['installation_contract']['verify_command']}\n"
        '```\n\n'
        f"Observed Python minor version: `{snapshot['python']['minor_version']}`\n\n"
        f"Observed required-import readiness: `{validation['required_imports_ready']}`\n\n"
        f"Observed missing imports: `{missing_imports}`\n\n"
        f"Release workflow path: `{workflow_path}`\n\n"
        f"Checkpoint wrapper path: `{wrapper_path}`\n"
    )


def _bootstrap_script(snapshot: Mapping[str, Any]) -> str:
    commands = '\n'.join(snapshot['installation_contract']['bootstrap_commands'])
    return '#!/usr/bin/env bash\nset -euo pipefail\n' + commands + '\n'


def write_certification_environment_bundle(
    root: str | Path,
    *,
    bundle_root: str | Path | None = None,
    release_root: str | Path | None = None,
    bundle_name: str = DEFAULT_BUNDLE_NAME,
    workflow_path: str = DEFAULT_RELEASE_WORKFLOW,
    wrapper_path: str = DEFAULT_WRAPPER,
    command: Sequence[str] | None = None,
    require_ready: bool = False,
) -> dict[str, Any]:
    repo_root = Path(root)
    if bundle_root is None:
        if release_root is None:
            raise ValueError('bundle_root or release_root must be provided')
        bundle_path = Path(release_root) / bundle_name
    else:
        bundle_path = Path(bundle_root)
    bundle_path.mkdir(parents=True, exist_ok=True)

    snapshot = build_certification_environment_snapshot(
        repo_root,
        command=command,
        workflow_path=workflow_path,
        wrapper_path=wrapper_path,
    )
    try:
        artifact_root = str(bundle_path.relative_to(repo_root)).replace('\\', '/')
    except ValueError:
        artifact_root = str(bundle_path).replace('\\', '/')
    environment_file = 'environment.json'
    manifest = _bundle_manifest(bundle_path, artifact_root, snapshot, workflow_path=workflow_path, wrapper_path=wrapper_path)
    index = _bundle_index(
        bundle_path,
        artifact_root,
        snapshot,
        workflow_path=workflow_path,
        wrapper_path=wrapper_path,
        environment_file=environment_file,
    )
    summary = _bundle_summary(index)

    (bundle_path / 'environment.json').write_text(json.dumps(snapshot, indent=2) + '\n', encoding='utf-8')
    (bundle_path / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (bundle_path / 'index.json').write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')
    (bundle_path / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (bundle_path / 'README.md').write_text(_bundle_readme(snapshot, workflow_path=workflow_path, wrapper_path=wrapper_path), encoding='utf-8')
    bootstrap = bundle_path / 'bootstrap.sh'
    bootstrap.write_text(_bootstrap_script(snapshot), encoding='utf-8')
    bootstrap.chmod(0o755)

    if require_ready and not snapshot['validation']['environment_ready_for_release_workflow']:
        missing = ', '.join(snapshot['validation']['missing_imports']) or 'python version mismatch'
        raise CertificationEnvironmentError(
            'certification environment is not ready: '
            f"python_ready={snapshot['validation']['python_version_ready']} "
            f"required_imports_ready={snapshot['validation']['required_imports_ready']} "
            f"missing={missing}"
        )
    return snapshot


def build_status_payload(
    snapshot: Mapping[str, Any],
    *,
    release_root: str,
    bundle_root: str,
    workflow_path: str = DEFAULT_RELEASE_WORKFLOW,
    wrapper_path: str = DEFAULT_WRAPPER,
) -> dict[str, Any]:
    validation = snapshot['validation']
    return {
        'checkpoint': 'certification_environment_freeze',
        'phase': 'step1_execution_environment_freeze',
        'status': 'environment_ready' if validation['environment_ready_for_release_workflow'] else 'environment_contract_frozen_but_not_ready',
        'current_state': {
            'required_install_command': snapshot['installation_contract']['install_command'],
            'required_verify_command': snapshot['installation_contract']['verify_command'],
            'required_extras': list(snapshot['installation_contract']['required_extras']),
            'required_imports': list(validation['required_imports']),
            'required_imports_ready': validation['required_imports_ready'],
            'missing_imports': list(validation['missing_imports']),
            'python_minor_version': snapshot['python']['minor_version'],
            'python_version_ready': validation['python_version_ready'],
            'environment_ready_for_release_workflow': validation['environment_ready_for_release_workflow'],
            'release_root': release_root,
            'bundle_root': bundle_root,
            'workflow_path': workflow_path,
            'wrapper_path': wrapper_path,
        },
        'validation': {
            'python_version_ready': validation['python_version_ready'],
            'required_imports_ready': validation['required_imports_ready'],
            'missing_imports': list(validation['missing_imports']),
            'supported_release_workflow_versions': list(snapshot['python']['supported_release_workflow_versions']),
        },
        'notes': [
            'The release workflow must install the package with both the certification and dev extras before any Phase 9 checkpoint script is executed.',
            'The local/offline checkpoint environment may still be non-ready even when the installation contract has been frozen; current readiness is recorded, not assumed.',
            'This checkpoint closes the operational ambiguity around how the strict-promotion environment is provisioned, but it does not by itself turn the strict RFC target green.',
        ],
    }


def build_status_markdown(payload: Mapping[str, Any]) -> str:
    state = payload['current_state']
    missing = ', '.join(state['missing_imports']) if state['missing_imports'] else 'none'
    return (
        '# Certification environment freeze\n\n'
        'This checkpoint freezes the certification-environment installation contract for the strict-promotion workflow.\n\n'
        '## Required bootstrap\n\n'
        '```bash\n'
        'python -m venv .venv\n'
        'source .venv/bin/activate\n'
        'python -m pip install -U pip\n'
        f"{state['required_install_command']}\n"
        f"{state['required_verify_command']}\n"
        '```\n\n'
        '## Current recorded state\n\n'
        f"- python minor version: `{state['python_minor_version']}`\n"
        f"- python version ready for the release workflow: `{state['python_version_ready']}`\n"
        f"- required imports ready: `{state['required_imports_ready']}`\n"
        f"- missing imports: `{missing}`\n"
        f"- environment ready for the release workflow: `{state['environment_ready_for_release_workflow']}`\n"
        f"- release workflow path: `{state['workflow_path']}`\n"
        f"- wrapper path: `{state['wrapper_path']}`\n"
        f"- preserved bundle root: `{state['bundle_root']}`\n\n"
        '## What this checkpoint changes\n\n'
        '- makes the strict-promotion installation contract explicit\n'
        '- records the observed environment snapshot in a preserved certification bundle\n'
        '- adds a release-workflow guard that fails when the required imports are missing\n'
        '- adds a local wrapper that freezes the environment before invoking Phase 9 checkpoint scripts\n\n'
        '## Honest current result\n\n'
        'This update improves the package operationally, but it does **not** by itself make the package certifiably fully featured or strict-target fully RFC compliant. The remaining strict-target HTTP/3 evidence blockers still need to be closed separately.\n'
    )


def write_status_documents(
    root: str | Path,
    snapshot: Mapping[str, Any],
    *,
    release_root: str,
    bundle_root: str,
    workflow_path: str = DEFAULT_RELEASE_WORKFLOW,
    wrapper_path: str = DEFAULT_WRAPPER,
    status_doc: str = DEFAULT_STATUS_DOC,
    status_json: str = DEFAULT_STATUS_JSON,
    delivery_notes: str = DEFAULT_DELIVERY_NOTES,
) -> dict[str, Any]:
    repo_root = Path(root)
    payload = build_status_payload(
        snapshot,
        release_root=release_root,
        bundle_root=bundle_root,
        workflow_path=workflow_path,
        wrapper_path=wrapper_path,
    )
    markdown = build_status_markdown(payload)
    (repo_root / status_doc).write_text(markdown, encoding='utf-8')
    (repo_root / status_json).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    (repo_root / delivery_notes).write_text(
        '# Delivery notes — certification environment freeze\n\n'
        'This checkpoint freezes the strict-promotion installation contract, adds a certification-environment bundle, and wires the requirement into a release-workflow guard and a local checkpoint wrapper.\n\n'
        'It does **not** claim that the package is already strict-target green; it only closes the environment-provisioning ambiguity that previously allowed the remaining HTTP/3 third-party scenarios to run without the required extras installed.\n',
        encoding='utf-8',
    )
    return payload
