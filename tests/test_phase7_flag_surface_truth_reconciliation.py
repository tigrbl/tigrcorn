from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path

from tigrcorn.cli import build_parser


class Phase7FlagSurfaceTruthReconciliationTests(unittest.TestCase):
    def _public_parser_flags(self) -> set[str]:
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

    def test_markdown_flag_surface_mentions_tls_material_flags_and_alt_svc_rows(self) -> None:
        text = Path('docs/review/conformance/CLI_FLAG_SURFACE.md').read_text(encoding='utf-8')
        for needle in [
            '--ssl-keyfile-password',
            '--ssl-crl',
            '--alt-svc',
            '--alt-svc-auto',
            '--alt-svc-ma',
            '--alt-svc-persist',
        ]:
            self.assertIn(needle, text)

    def test_machine_readable_flag_surface_matches_current_parser(self) -> None:
        payload = json.loads(Path('docs/review/conformance/cli_flag_surface.json').read_text(encoding='utf-8'))
        parser_flags = self._public_parser_flags()
        documented_flags = {flag for row in payload['flags'] for flag in row['flags']}
        self.assertEqual(documented_flags, parser_flags)
        self.assertEqual(payload['public_flag_string_count'], len(parser_flags))
        self.assertEqual(payload['promotion_ready_count'], len(parser_flags))
        tls_row = next(row for row in payload['flags'] if row['flag_id'] == 'tls')
        self.assertIn('--ssl-keyfile-password', tls_row['flags'])
        self.assertIn('--ssl-crl', tls_row['flags'])

    def test_help_snapshot_matches_current_cli_help(self) -> None:
        snapshot = Path('docs/review/conformance/cli_help.current.txt').read_text(encoding='utf-8')
        self.assertEqual(snapshot, build_parser().format_help())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
