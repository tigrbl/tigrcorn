from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tigrcorn.compat.interop_runner import (  # noqa: E402
    INTEROP_ARTIFACT_SCHEMA_VERSION,
    INTEROP_BUNDLE_REQUIRED_FILES,
    INTEROP_SCENARIO_REQUIRED_FILES,
    run_external_matrix,
)
from tigrcorn.compat.release_gates import assert_independent_certification_bundle_ready  # noqa: E402
from tools.interop_wrappers import describe_wrapper_registry  # noqa: E402

CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.8' / 'release-0.3.8'
BUNDLE_ROOT = RELEASE_ROOT / 'tigrcorn-independent-harness-foundation-bundle'
MATRIX_PATH = CONFORMANCE / 'external_matrix.release.json'
PROOF_SCENARIOS = ['http1-server-curl-client']
COMMIT_HASH = 'phase9b-independent-harness-foundation'


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _rewrite_payload(value: Any, *, source_root: str, destination_root: str) -> Any:
    if isinstance(value, str):
        return value.replace(source_root, destination_root)
    if isinstance(value, list):
        return [_rewrite_payload(item, source_root=source_root, destination_root=destination_root) for item in value]
    if isinstance(value, dict):
        return {
            key: _rewrite_payload(item, source_root=source_root, destination_root=destination_root)
            for key, item in value.items()
        }
    return value


def _normalize_bundle_paths(bundle_root: Path, *, source_root: str) -> None:
    destination_root = str(bundle_root.relative_to(ROOT))
    for json_file in bundle_root.rglob('*.json'):
        payload = _load_json(json_file)
        payload = _rewrite_payload(payload, source_root=source_root, destination_root=destination_root)
        _write_json(json_file, payload)


def main() -> int:
    wrapper_registry = describe_wrapper_registry()
    with tempfile.TemporaryDirectory() as artifact_root:
        previous_commit = os.environ.get('TIGRCORN_COMMIT_HASH')
        os.environ['TIGRCORN_COMMIT_HASH'] = COMMIT_HASH
        try:
            summary = run_external_matrix(
                MATRIX_PATH,
                artifact_root=artifact_root,
                source_root=ROOT,
                scenario_ids=PROOF_SCENARIOS,
                strict=True,
            )
        finally:
            if previous_commit is None:
                os.environ.pop('TIGRCORN_COMMIT_HASH', None)
            else:
                os.environ['TIGRCORN_COMMIT_HASH'] = previous_commit

        generated_root = Path(summary.artifact_root)
        if BUNDLE_ROOT.exists():
            shutil.rmtree(BUNDLE_ROOT)
        shutil.copytree(generated_root, BUNDLE_ROOT)

    _normalize_bundle_paths(BUNDLE_ROOT, source_root=str(generated_root))

    manifest = _load_json(BUNDLE_ROOT / 'manifest.json')
    manifest.update(
        {
            'bundle_kind': 'independent_harness_foundation',
            'phase': '9B',
            'release': '0.3.8',
            'proof_scenarios': PROOF_SCENARIOS,
            'release_gate_eligible': False,
            'strict_target_complete': False,
            'source_matrix': str(MATRIX_PATH.relative_to(ROOT)),
            'wrapper_registry_module': wrapper_registry['module'],
            'wrapper_families': wrapper_registry['families'],
            'artifact_schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
            'required_bundle_files': list(INTEROP_BUNDLE_REQUIRED_FILES),
            'required_scenario_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
        }
    )
    _write_json(BUNDLE_ROOT / 'manifest.json', manifest)

    summary_payload = _load_json(BUNDLE_ROOT / 'summary.json')
    summary_payload.update(
        {
            'bundle_kind': 'independent_harness_foundation',
            'phase': '9B',
            'release': '0.3.8',
            'proof_scenarios': PROOF_SCENARIOS,
            'release_gate_eligible': False,
            'strict_target_complete': False,
        }
    )
    _write_json(BUNDLE_ROOT / 'summary.json', summary_payload)

    index_payload = _load_json(BUNDLE_ROOT / 'index.json')
    index_payload.update(
        {
            'bundle_kind': 'independent_harness_foundation',
            'phase': '9B',
            'release': '0.3.8',
            'proof_scenarios': PROOF_SCENARIOS,
            'release_gate_eligible': False,
            'strict_target_complete': False,
        }
    )
    _write_json(BUNDLE_ROOT / 'index.json', index_payload)

    (BUNDLE_ROOT / 'README.md').write_text(
        '# Phase 9B independent harness foundation bundle\n\n'
        'This bundle is the Phase 9B proof bundle for the shared independent-certification harness.\n\n'
        'It intentionally contains one rerun already-green scenario:\n\n'
        '- `http1-server-curl-client`\n\n'
        'The bundle is **not** a full strict-target certification bundle and does **not** by itself make the repository promotion-ready.\n',
        encoding='utf-8',
    )

    assert_independent_certification_bundle_ready(BUNDLE_ROOT, required_scenarios=PROOF_SCENARIOS)

    release_manifest = _load_json(RELEASE_ROOT / 'manifest.json')
    release_manifest.update(
        {
            'status': 'phase9b_harness_foundation_complete_not_yet_promotable',
            'promotion_ready': False,
            'strict_target_complete': False,
            'source_checkpoint': 'phase9b_independent_harness_foundation',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'bundles': {
                'independent_harness_foundation': {
                    'path': str(BUNDLE_ROOT.relative_to(ROOT)),
                    'scenario_count': len(PROOF_SCENARIOS),
                    'proof_scenarios': PROOF_SCENARIOS,
                    'validated': True,
                    'release_gate_eligible': False,
                    'artifact_schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                }
            },
            'notes': [
                'This release root now contains the Phase 9B independent harness foundation proof bundle.',
                'The proof bundle demonstrates standardized wrapper-driven artifact generation for one already-green independent scenario.',
                'The release root remains non-promotable because the strict boundary, public flag closure, and strict performance target are still incomplete.',
            ],
        }
    )
    _write_json(RELEASE_ROOT / 'manifest.json', release_manifest)

    (RELEASE_ROOT / 'README.md').write_text(
        '# Release 0.3.8 working promotion root\n\n'
        'This directory remains the next promotable release root reserved by Phase 9A.\n\n'
        'Phase 9B adds the shared independent-certification harness foundation proof bundle at:\n\n'
        '- `tigrcorn-independent-harness-foundation-bundle/`\n\n'
        'Current truth:\n\n'
        '- the release root is **not** yet promotable\n'
        '- the strict target is **not** yet complete\n'
        '- the bundle exists to prove the reusable harness and artifact schema, not to claim final certification\n',
        encoding='utf-8',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
