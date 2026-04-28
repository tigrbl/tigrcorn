from __future__ import annotations

from tigrcorn_config.load import config_from_source
from tigrcorn_runtime.server.bootstrap import run_config


def main() -> int:
    config = config_from_source("examples/websocket_uix_demo/server.config.json")
    run_config(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

