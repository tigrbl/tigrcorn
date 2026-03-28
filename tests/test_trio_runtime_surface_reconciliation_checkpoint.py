from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path

from tigrcorn.cli import build_parser
from tigrcorn.compat.release_gates import evaluate_promotion_target
from tigrcorn.config.load import config_from_mapping
from tigrcorn.errors import ConfigError
from tigrcorn.server.bootstrap import run_coro_with_runtime, runtime_compatibility_matrix

ROOT = Path(__file__).resolve().parents[1]


class TrioRuntimeSurfaceReconciliationCheckpointTests(unittest.TestCase):
    def test_parser_runtime_choices_no_longer_include_trio(self) -> None:
        parser = build_parser()
        runtime_action = next(action for action in parser._actions if '--runtime' in action.option_strings)
        self.assertEqual(tuple(runtime_action.choices), ('auto', 'asyncio', 'uvloop'))
        with self.assertRaises(SystemExit):
            parser.parse_args(['tests.fixtures_pkg.appmod:app', '--runtime', 'trio'])

    def test_config_validation_rejects_trio_runtime_and_worker_class(self) -> None:
        with self.assertRaises(ConfigError):
            config_from_mapping({'app': {'target': 'tests.fixtures_pkg.appmod:app'}, 'process': {'runtime': 'trio'}})
        with self.assertRaises(ConfigError):
            config_from_mapping({'app': {'target': 'tests.fixtures_pkg.appmod:app'}, 'process': {'worker_class': 'trio'}})

    def test_runtime_matrix_and_docs_descoped_trio(self) -> None:
        expected = runtime_compatibility_matrix()
        self.assertEqual(set(expected), {'auto', 'asyncio', 'uvloop'})
        for rel in [
            'docs/review/conformance/phase4_advanced_delivery/runtime_compatibility_matrix.json',
            'docs/review/conformance/phase4_advanced_protocol_delivery/runtime_compatibility_matrix.json',
        ]:
            payload = json.loads((ROOT / rel).read_text(encoding='utf-8'))
            self.assertEqual(payload, expected)

    def test_direct_runtime_invocation_rejects_trio(self) -> None:
        with self.assertRaises(RuntimeError):
            run_coro_with_runtime(lambda: None, runtime='trio')

    def test_promotion_target_remains_green(self) -> None:
        report = evaluate_promotion_target(ROOT)
        self.assertTrue(report.passed, msg=report.failures)
