import os
import sys
import tempfile
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

    def test_load_app_from_current_working_directory_without_app_dir(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            app_path = os.path.join(td, 'app.py')
            with open(app_path, 'w', encoding='utf-8') as handle:
                handle.write('async def app(scope, receive, send):\n    return None\n')
            previous = os.getcwd()
            original_sys_path = list(sys.path)
            try:
                os.chdir(td)
                sys.path[:] = [entry for entry in sys.path if entry not in ('', td)]
                loaded = load_app('app:app')
                self.assertTrue(callable(loaded))
            finally:
                sys.modules.pop('app', None)
                sys.path[:] = original_sys_path
                os.chdir(previous)

    def test_load_factory_from_current_working_directory_without_app_dir(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            app_path = os.path.join(td, 'app.py')
            with open(app_path, 'w', encoding='utf-8') as handle:
                handle.write('def factory():\n    async def app(scope, receive, send):\n        return None\n    return app\n')
            previous = os.getcwd()
            original_sys_path = list(sys.path)
            try:
                os.chdir(td)
                sys.path[:] = [entry for entry in sys.path if entry not in ('', td)]
                loaded = load_app('app:factory', factory=True)
                self.assertTrue(callable(loaded))
            finally:
                sys.modules.pop('app', None)
                sys.path[:] = original_sys_path
                os.chdir(previous)
