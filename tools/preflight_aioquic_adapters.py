from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.aioquic_preflight import (  # noqa: E402
    AioquicAdapterPreflightError,
    run_aioquic_adapter_preflight,
    write_status_documents,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the direct third-party aioquic HTTP/3 adapter preflight and preserve the resulting bundle.'
    )
    parser.add_argument(
        '--release-root',
        default='docs/review/conformance/releases/0.3.8/release-0.3.8',
        help='Repository-relative release root where the preserved preflight bundle should be written by default.',
    )
    parser.add_argument(
        '--bundle-name',
        default='tigrcorn-aioquic-adapter-preflight-bundle',
        help='Bundle name used under the release root when --bundle-root is not supplied.',
    )
    parser.add_argument(
        '--bundle-root',
        help='Optional explicit bundle target path. When omitted, the bundle is written under the release root.',
    )
    parser.add_argument(
        '--status-doc',
        default='docs/review/conformance/AIOQUIC_ADAPTER_PREFLIGHT.md',
        help='Repository-relative markdown status document path.',
    )
    parser.add_argument(
        '--status-json',
        default='docs/review/conformance/aioquic_adapter_preflight.current.json',
        help='Repository-relative machine-readable status path.',
    )
    parser.add_argument(
        '--delivery-notes',
        default='DELIVERY_NOTES_AIOQUIC_ADAPTER_PREFLIGHT.md',
        help='Repository-relative delivery-notes path.',
    )
    parser.add_argument(
        '--skip-status-docs',
        action='store_true',
        help='Only write the preserved bundle; do not refresh repository status documents.',
    )
    parser.add_argument(
        '--require-pass',
        action='store_true',
        help='Fail when either aioquic adapter preflight scenario does not pass.',
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    resolved_bundle_root = None if args.bundle_root is None else ROOT / args.bundle_root
    try:
        snapshot = run_aioquic_adapter_preflight(
            ROOT,
            release_root=args.release_root,
            bundle_name=args.bundle_name,
            bundle_root=resolved_bundle_root,
            require_pass=args.require_pass,
        )
    except AioquicAdapterPreflightError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    bundle_root = snapshot['current_state']['bundle_root']
    if not args.skip_status_docs:
        write_status_documents(
            ROOT,
            snapshot,
            release_root=args.release_root,
            bundle_root=bundle_root,
            status_doc=args.status_doc,
            status_json=args.status_json,
            delivery_notes=args.delivery_notes,
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
