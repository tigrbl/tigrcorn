from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.certification_env import (  # noqa: E402
    CertificationEnvironmentError,
    DEFAULT_BUNDLE_NAME,
    DEFAULT_RELEASE_WORKFLOW,
    DEFAULT_STATUS_DOC,
    DEFAULT_STATUS_JSON,
    DEFAULT_WRAPPER,
    write_certification_environment_bundle,
    write_status_documents,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Freeze and record the certification environment contract.')
    parser.add_argument(
        '--release-root',
        default='docs/review/conformance/releases/0.3.8/release-0.3.8',
        help='Repository-relative release root that should receive the preserved certification-environment bundle.',
    )
    parser.add_argument(
        '--bundle-name',
        default=DEFAULT_BUNDLE_NAME,
        help='Bundle directory name when --bundle-root is not provided.',
    )
    parser.add_argument(
        '--bundle-root',
        default=None,
        help='Explicit repository-relative bundle root. Overrides --release-root/--bundle-name when set.',
    )
    parser.add_argument(
        '--workflow-path',
        default=DEFAULT_RELEASE_WORKFLOW,
        help='Repository-relative workflow path recorded in the frozen snapshot.',
    )
    parser.add_argument(
        '--wrapper-path',
        default=DEFAULT_WRAPPER,
        help='Repository-relative wrapper path recorded in the frozen snapshot.',
    )
    parser.add_argument(
        '--status-doc',
        default=DEFAULT_STATUS_DOC,
        help='Repository-relative markdown status document path.',
    )
    parser.add_argument(
        '--status-json',
        default=DEFAULT_STATUS_JSON,
        help='Repository-relative machine-readable status path.',
    )
    parser.add_argument(
        '--skip-status-docs',
        action='store_true',
        help='Only write the bundle; do not update repository status documents.',
    )
    parser.add_argument(
        '--require-imports',
        action='store_true',
        help='Fail if the current environment does not satisfy the frozen release-workflow contract.',
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    bundle_root = None if args.bundle_root is None else ROOT / args.bundle_root
    release_root = ROOT / args.release_root
    try:
        snapshot = write_certification_environment_bundle(
            ROOT,
            bundle_root=bundle_root,
            release_root=release_root,
            bundle_name=args.bundle_name,
            workflow_path=args.workflow_path,
            wrapper_path=args.wrapper_path,
            command=[sys.executable, *sys.argv],
            require_ready=args.require_imports,
        )
    except CertificationEnvironmentError as exc:
        bundle_target = bundle_root if bundle_root is not None else release_root / args.bundle_name
        if not args.skip_status_docs:
            write_status_documents(
                ROOT,
                write_certification_environment_bundle(
                    ROOT,
                    bundle_root=bundle_target,
                    workflow_path=args.workflow_path,
                    wrapper_path=args.wrapper_path,
                    command=[sys.executable, *sys.argv],
                    require_ready=False,
                ),
                release_root=args.release_root,
                bundle_root=str(bundle_target.relative_to(ROOT)),
                workflow_path=args.workflow_path,
                wrapper_path=args.wrapper_path,
                status_doc=args.status_doc,
                status_json=args.status_json,
            )
        print(str(exc), file=sys.stderr)
        return 1

    bundle_target = bundle_root if bundle_root is not None else release_root / args.bundle_name
    if not args.skip_status_docs:
        write_status_documents(
            ROOT,
            snapshot,
            release_root=args.release_root,
            bundle_root=str(bundle_target.relative_to(ROOT)),
            workflow_path=args.workflow_path,
            wrapper_path=args.wrapper_path,
            status_doc=args.status_doc,
            status_json=args.status_json,
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
