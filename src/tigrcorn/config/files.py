from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any

try:  # pragma: no cover
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


class ConfigFileError(RuntimeError):
    pass


def load_config_file(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigFileError(f"config file does not exist: {config_path}")
    suffix = config_path.suffix.lower()
    if suffix == ".json":
        return json.loads(config_path.read_text(encoding="utf-8"))
    if suffix == ".toml":
        if tomllib is None:
            raise ConfigFileError("TOML loading is unavailable on this Python runtime")
        return tomllib.loads(config_path.read_text(encoding="utf-8"))
    if suffix == ".py":
        payload = runpy.run_path(str(config_path))
        for key in ("CONFIG", "config", "TIGRCORN_CONFIG"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        raise ConfigFileError(f"python config {config_path} did not expose CONFIG/config/TIGRCORN_CONFIG")
    raise ConfigFileError(f"unsupported config file type: {config_path.suffix!r}")
