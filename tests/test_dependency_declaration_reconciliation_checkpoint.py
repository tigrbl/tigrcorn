from __future__ import annotations

import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from tigrcorn.config.files import ConfigFileError, load_config_file
from tigrcorn.protocols.content_coding import encode_content

ROOT = Path(__file__).resolve().parents[1]


class DependencyDeclarationReconciliationCheckpointTests(unittest.TestCase):
    def test_pyproject_declares_optional_install_paths(self) -> None:
        payload = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        extras = payload['project']['optional-dependencies']

        self.assertIn('config-yaml', extras)
        self.assertTrue(any(dep.startswith('PyYAML') for dep in extras['config-yaml']))

        self.assertIn('compression', extras)
        self.assertTrue(any(dep.startswith('brotli') for dep in extras['compression']))

        self.assertIn('runtime-uvloop', extras)
        self.assertTrue(any(dep.startswith('uvloop') for dep in extras['runtime-uvloop']))

        self.assertIn('runtime-trio', extras)
        self.assertTrue(any(dep.startswith('trio') for dep in extras['runtime-trio']))

        self.assertIn('full-featured', extras)
        full_featured = extras['full-featured']
        self.assertTrue(any(dep.startswith('PyYAML') for dep in full_featured))
        self.assertTrue(any(dep.startswith('brotli') for dep in full_featured))
        self.assertTrue(any(dep.startswith('uvloop') for dep in full_featured))
        self.assertFalse(any(dep.startswith('trio') for dep in full_featured))

        dev = extras['dev']
        self.assertTrue(any(dep.startswith('pytest') for dep in dev))
        self.assertTrue(any(dep.startswith('PyYAML') for dep in dev))
        self.assertTrue(any(dep.startswith('brotli') for dep in dev))
        self.assertTrue(any(dep.startswith('uvloop') for dep in dev))

    def test_docs_reference_declared_optional_surfaces(self) -> None:
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        optional_doc = (ROOT / 'docs/review/conformance/OPTIONAL_DEPENDENCY_SURFACE.md').read_text(encoding='utf-8')
        docs_readme = (ROOT / 'docs/review/conformance/README.md').read_text(encoding='utf-8')
        pairing = (ROOT / 'examples/PHASE4_PROTOCOL_PAIRING.md').read_text(encoding='utf-8')

        for token in ('config-yaml', 'compression', 'runtime-uvloop', 'runtime-trio', 'full-featured'):
            self.assertIn(token, readme)
            self.assertIn(token, optional_doc)
        self.assertIn('OPTIONAL_DEPENDENCY_SURFACE.md', docs_readme)
        self.assertIn('runtime `trio` is **not** part of the supported public runtime surface', pairing)
        self.assertNotIn('surfaced-but-not-yet-wired execution mode', pairing)

    def test_optional_dependency_error_hints_point_to_declared_extras(self) -> None:
        yaml_config = ROOT / 'tests/fixtures_pkg/phase1_yaml_missing.yaml'
        yaml_config.write_text('app:\n  target: tests.fixtures_pkg.appmod:app\n', encoding='utf-8')
        try:
            with patch('tigrcorn.config.files.yaml', None):
                with self.assertRaises(ConfigFileError) as ctx:
                    load_config_file(yaml_config)
            self.assertIn('tigrcorn[config-yaml]', str(ctx.exception))
        finally:
            yaml_config.unlink(missing_ok=True)

        with patch('tigrcorn.protocols.content_coding.brotli', None):
            with self.assertRaises(RuntimeError) as ctx:
                encode_content('br', b'payload')
        self.assertIn('tigrcorn[compression]', str(ctx.exception))

        bootstrap_source = (ROOT / 'src/tigrcorn/server/bootstrap.py').read_text(encoding='utf-8')
        self.assertIn('tigrcorn[runtime-uvloop]', bootstrap_source)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
