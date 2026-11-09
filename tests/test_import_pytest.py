import importlib


def test_import() -> None:
    mod = importlib.import_module("tigrcorn")
    assert hasattr(mod, "run")
