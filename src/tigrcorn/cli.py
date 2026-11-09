from __future__ import annotations

import argparse
import json
import sys

import tigrcorn_runtime.cli as _runtime_cli
from tigrcorn_runtime.cli import build_parser as build_server_parser
from tigrcorn_runtime.server.bootstrap import run_config


def _capabilities_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tigrcorn inspect capabilities")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON capability registry output")
    parser.add_argument("--profile", default="default", help="Blessed deployment profile to inspect")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        dest="required_capabilities",
        help="Require a capability id to be enabled for the selected profile",
    )
    return parser


def _inspect_capabilities(argv: list[str]) -> int:
    from . import capabilities

    parser = _capabilities_parser()
    ns = parser.parse_args(argv)
    if ns.required_capabilities:
        try:
            capabilities.require_supported(ns.required_capabilities, profile=ns.profile)
        except capabilities.UnsupportedCapabilityError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    payload = capabilities.export(profile=ns.profile)
    if not ns.as_json:
        parser.error("inspect capabilities currently requires --json")
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


def _certify(argv: list[str]) -> int:
    if not argv:
        print("missing certification surface", file=sys.stderr)
        return 2
    surface, *surface_argv = argv
    if surface != "static":
        print(f"unknown certification surface: {surface}", file=sys.stderr)
        return 2

    from . import capabilities
    from tigrcorn_certification.certify.static import certify_static_main

    return certify_static_main(surface_argv, require_supported=capabilities.require_supported)


def build_parser() -> argparse.ArgumentParser:
    return build_server_parser()


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv[:2] == ["inspect", "capabilities"]:
        return _inspect_capabilities(effective_argv[2:])
    if effective_argv[:1] == ["certify"]:
        return _certify(effective_argv[1:])
    _runtime_cli.run_config = run_config
    return _runtime_cli.main(effective_argv)
