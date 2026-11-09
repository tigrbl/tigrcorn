from __future__ import annotations

from importlib import resources
from typing import Any
import json


SCHEMA_NAME = "runtime-capability-registry.schema.json"


def read_schema_text() -> str:
    return resources.files(__package__).joinpath(SCHEMA_NAME).read_text(encoding="utf-8")


def load_schema() -> dict[str, Any]:
    payload = json.loads(read_schema_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{SCHEMA_NAME} did not contain a JSON object")
    return payload
