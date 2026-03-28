from __future__ import annotations

import asyncio

from tigrcorn.config.load import config_from_mapping
from tigrcorn.server.bootstrap import serve_from_config


async def on_startup(server) -> None:
    server.logger.info('phase4 embedding startup hook fired')


async def on_shutdown(server) -> None:
    server.logger.info('phase4 embedding shutdown hook fired')


CONFIG = {
    'app': {'target': 'examples.echo_http.app:app'},
    'listeners': [{'kind': 'tcp', 'host': '127.0.0.1', 'port': 8000}],
    'hooks': {'on_startup': [on_startup], 'on_shutdown': [on_shutdown]},
}


async def main() -> None:
    config = config_from_mapping(CONFIG)
    await serve_from_config(config)


if __name__ == '__main__':  # pragma: no cover
    asyncio.run(main())
