import unittest

from tigrcorn.errors import AppLoadError
from tigrcorn.server.app_loader import load_app
from tigrcorn.utils.imports import import_from_string


class AppLoaderTests(unittest.TestCase):
    def test_import_from_string(self):
        obj = import_from_string('tests.fixtures_pkg.appmod:app')
        self.assertTrue(callable(obj))

    def test_load_app(self):
        app = load_app('tests.fixtures_pkg.appmod:app')
        self.assertTrue(callable(app))

    def test_load_factory(self):
        app = load_app('tests.fixtures_pkg.appmod:factory', factory=True)
        self.assertTrue(callable(app))

    def test_bad_import_raises(self):
        with self.assertRaises(AppLoadError):
            load_app('tests.fixtures_pkg.appmod:missing')
