from __future__ import annotations

from tigrcorn.config.load import build_config
from tigrcorn.server.app_loader import load_app
from tigrcorn.server.runner import TigrCornServer


def bootstrap(app_target: str, **kwargs) -> TigrCornServer:
    config = build_config(app=app_target, **kwargs)
    app = load_app(app_target, factory=bool(kwargs.get("factory", False)))
    return TigrCornServer(app=app, config=config)
