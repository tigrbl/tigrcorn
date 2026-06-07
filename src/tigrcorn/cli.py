from __future__ import annotations

import argparse
import json
import sys

from tigrcorn_runtime.cli import build_parser as build_server_parser
from tigrcorn_runtime.cli import main as _server_main


def _capabilities_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tigrcorn inspect capabilities")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON capability registry output")
    parser.add_argument("--profile", default="default", help="Blessed deployment profile to inspect")
    return parser


def _inspect_capabilities(argv: list[str]) -> int:
    from . import capabilities

    parser = _capabilities_parser()
    ns = parser.parse_args(argv)
    payload = capabilities.export(profile=ns.profile)
    if not ns.as_json:
        parser.error("inspect capabilities currently requires --json")
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


def build_parser() -> argparse.ArgumentParser:
    return build_server_parser()


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv[:2] == ["inspect", "capabilities"]:
        return _inspect_capabilities(effective_argv[2:])
    return _server_main(effective_argv)
