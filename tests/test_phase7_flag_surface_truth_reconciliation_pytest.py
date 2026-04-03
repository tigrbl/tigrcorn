from __future__ import annotations

import argparse
import json
from pathlib import Path

from tigrcorn.cli import build_parser


def _public_parser_flags() -> set[str]:
    parser = build_parser()
    flags: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if action.help == argparse.SUPPRESS:
            continue
        for option in action.option_strings:
            if option.startswith('--'):
                flags.add(option)
    return flags


def test_markdown_flag_surface_mentions_tls_material_flags_and_alt_svc_rows() -> None:
    text = Path('docs/review/conformance/CLI_FLAG_SURFACE.md').read_text(encoding='utf-8')
    for needle in [
        '--ssl-keyfile-password',
        '--ssl-crl',
        '--alt-svc',
        '--alt-svc-auto',
        '--alt-svc-ma',
        '--alt-svc-persist',
    ]:
        assert needle in text


def test_machine_readable_flag_surface_matches_current_parser() -> None:
    payload = json.loads(
        Path('docs/review/conformance/cli_flag_surface.json').read_text(encoding='utf-8')
    )
    parser_flags = _public_parser_flags()
    documented_flags = {flag for row in payload['flags'] for flag in row['flags']}
    assert documented_flags == parser_flags
    assert payload['public_flag_string_count'] == len(parser_flags)
    assert payload['promotion_ready_count'] == len(parser_flags)
    tls_row = next(row for row in payload['flags'] if row['flag_id'] == 'tls')
    assert '--ssl-keyfile-password' in tls_row['flags']
    assert '--ssl-crl' in tls_row['flags']


def test_help_snapshot_matches_current_cli_help() -> None:
    snapshot = Path('docs/review/conformance/cli_help.current.txt').read_text(
        encoding='utf-8'
    )
    assert snapshot == build_parser().format_help()
