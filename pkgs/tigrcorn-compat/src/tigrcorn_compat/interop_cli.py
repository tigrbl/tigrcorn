from __future__ import annotations

import argparse

from tigrcorn_certification.interop_runner import run_external_matrix



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='tigrcorn-interop', description='Run the tigrcorn external interoperability matrix and write evidence bundles')
    parser.add_argument('--matrix', required=True, help='Path to the external interop matrix JSON file')
    parser.add_argument('--output', required=True, help='Root directory for result bundles')
    parser.add_argument('--source-root', default='.', help='Repository root used for manifest hashing and commit detection')
    parser.add_argument('--only', action='append', dest='scenario_ids', help='Run only the named scenario id (may be given multiple times)')
    parser.add_argument('--strict', action='store_true', help='Stop after the first failed scenario')
    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    summary = run_external_matrix(
        ns.matrix,
        artifact_root=ns.output,
        source_root=ns.source_root,
        scenario_ids=ns.scenario_ids,
        strict=ns.strict,
    )
    return 0 if summary.failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
