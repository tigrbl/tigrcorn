from __future__ import annotations

import importlib


def import_from_string(target: str):
    if ":" not in target:
        raise ValueError(f"import string must be 'module:attr', got {target!r}")
    module_name, attr_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    obj = module
    for part in attr_name.split("."):
        obj = getattr(obj, part)
    return obj
