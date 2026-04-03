import os
import sys
import tempfile

import pytest

from tigrcorn.errors import AppLoadError
from tigrcorn.server.app_loader import load_app
from tigrcorn.utils.imports import import_from_string


def test_import_from_string() -> None:
    obj = import_from_string("tests.fixtures_pkg.appmod:app")
    assert callable(obj)


def test_load_app() -> None:
    app = load_app("tests.fixtures_pkg.appmod:app")
    assert callable(app)


def test_load_factory() -> None:
    app = load_app("tests.fixtures_pkg.appmod:factory", factory=True)
    assert callable(app)


def test_bad_import_raises() -> None:
    with pytest.raises(AppLoadError):
        load_app("tests.fixtures_pkg.appmod:missing")


def test_load_app_from_current_working_directory_without_app_dir() -> None:
    with tempfile.TemporaryDirectory() as td:
        app_path = os.path.join(td, "app.py")
        with open(app_path, "w", encoding="utf-8") as handle:
            handle.write("async def app(scope, receive, send):\n    return None\n")
        previous = os.getcwd()
        original_sys_path = list(sys.path)
        try:
            os.chdir(td)
            sys.path[:] = [entry for entry in sys.path if entry not in ("", td)]
            loaded = load_app("app:app")
            assert callable(loaded)
        finally:
            sys.modules.pop("app", None)
            sys.path[:] = original_sys_path
            os.chdir(previous)


def test_load_factory_from_current_working_directory_without_app_dir() -> None:
    with tempfile.TemporaryDirectory() as td:
        app_path = os.path.join(td, "app.py")
        with open(app_path, "w", encoding="utf-8") as handle:
            handle.write("def factory():\n    async def app(scope, receive, send):\n        return None\n    return app\n")
        previous = os.getcwd()
        original_sys_path = list(sys.path)
        try:
            os.chdir(td)
            sys.path[:] = [entry for entry in sys.path if entry not in ("", td)]
            loaded = load_app("app:factory", factory=True)
            assert callable(loaded)
        finally:
            sys.modules.pop("app", None)
            sys.path[:] = original_sys_path
            os.chdir(previous)
