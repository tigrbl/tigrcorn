from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_CHECKPOINT_SCRIPTS = (
    'tools/create_phase9b_harness_foundation.py',
    'tools/create_phase9c_rfc7692_checkpoint.py',
    'tools/create_phase9d1_connect_relay_checkpoint.py',
    'tools/create_phase9d2_trailer_fields_checkpoint.py',
    'tools/create_phase9d3_content_coding_checkpoint.py',
    'tools/create_phase9e_ocsp_checkpoint.py',
    'tools/create_phase9g_performance_checkpoint.py',
    'tools/create_phase9i_release_assembly_checkpoint.py',
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the Phase 9 release workflow only after freezing and validating the certification environment.'
    )
    parser.add_argument(
        '--scripts',
        nargs='*',
        default=list(DEFAULT_CHECKPOINT_SCRIPTS),
        help='Repository-relative Phase 9 checkpoint scripts to execute after the certification environment has been frozen.',
    )
    parser.add_argument(
        '--release-root',
        default='docs/review/conformance/releases/0.3.9/release-0.3.9',
        help='Release root passed through to the certification-environment freeze step.',
    )
    parser.add_argument(
        '--bundle-name',
        default='tigrcorn-certification-environment-bundle',
        help='Bundle name passed through to the certification-environment freeze step.',
    )
    parser.add_argument(
        '--skip-status-docs',
        action='store_true',
        help='Do not refresh repository status documents during the freeze step.',
    )
    return parser.parse_args()


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    args = _parse_args()
    freeze_command = [
        sys.executable,
        str(ROOT / 'tools' / 'freeze_certification_environment.py'),
        '--require-imports',
        '--release-root',
        args.release_root,
        '--bundle-name',
        args.bundle_name,
        '--workflow-path',
        '.github/workflows/phase9-certification-release.yml',
        '--wrapper-path',
        'tools/run_phase9_release_workflow.py',
    ]
    if args.skip_status_docs:
        freeze_command.append('--skip-status-docs')
    _run(freeze_command)

    preflight_command = [
        sys.executable,
        str(ROOT / 'tools' / 'preflight_aioquic_adapters.py'),
        '--require-pass',
        '--release-root',
        args.release_root,
        '--bundle-name',
        'tigrcorn-aioquic-adapter-preflight-bundle',
    ]
    if args.skip_status_docs:
        preflight_command.append('--skip-status-docs')
    _run(preflight_command)

    for script in args.scripts:
        _run([sys.executable, str(ROOT / script)])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
