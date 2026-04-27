from __future__ import annotations

from examples.wss_asgi3_lab.app import app
from tigrcorn.api import run
from tigrcorn.config.load import build_config


def main() -> None:
    config = build_config(
        app_interface="asgi3",
        host="127.0.0.1",
        port=8000,
        http_versions=["1.1"],
        websocket=True,
        protocols=["http1", "websocket"],
        lifespan="on",
        log_level="info",
    )
    config.websocket.compression = "permessage-deflate"
    config.websocket.max_message_size = 1_048_576
    config.websocket.ping_interval = 20
    config.websocket.ping_timeout = 20
    run(app, config=config)


if __name__ == "__main__":
    main()
