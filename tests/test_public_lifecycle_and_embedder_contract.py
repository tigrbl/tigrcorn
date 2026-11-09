from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from unittest import mock

from tigrcorn import EmbeddedServer
from tigrcorn.config.load import build_config
from tigrcorn.server.reloader import PollingReloader
from tigrcorn.server.runner import TigrCornServer


async def _http_ok_app(scope, receive, send):
    if scope['type'] == 'lifespan':
        message = await receive()
        assert message['type'] == 'lifespan.startup'
        await send({'type': 'lifespan.startup.complete'})
        message = await receive()
        assert message['type'] == 'lifespan.shutdown'
        await send({'type': 'lifespan.shutdown.complete'})
        return
    await receive()
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'text/plain')]})
    await send({'type': 'http.response.body', 'body': b'ok', 'more_body': False})


class Phase6LifecycleContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_and_shutdown_hooks_are_ordered_relative_to_lifespan(self) -> None:
        events: list[str] = []

        async def app(scope, receive, send):
            if scope['type'] == 'lifespan':
                message = await receive()
                events.append(message['type'])
                await send({'type': 'lifespan.startup.complete'})
                message = await receive()
                events.append(message['type'])
                await send({'type': 'lifespan.shutdown.complete'})
                return
            await receive()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

        async def on_start(server) -> None:
            self.assertTrue(server.lifespan.started)
            events.append('hook.startup')

        async def on_stop(server) -> None:
            events.append('hook.shutdown')

        config = build_config(host='127.0.0.1', port=0, lifespan='on')
        config.hooks.on_startup = [on_start]
        config.hooks.on_shutdown = [on_stop]

        server = TigrCornServer(app, config)
        await server.start()
        await server.close()

        self.assertEqual(
            events,
            ['lifespan.startup', 'hook.startup', 'lifespan.shutdown', 'hook.shutdown'],
        )

    async def test_startup_hook_failures_abort_startup(self) -> None:
        async def failing_start(_server) -> None:
            raise RuntimeError('startup failed')

        config = build_config(host='127.0.0.1', port=0, lifespan='off')
        config.hooks.on_startup = [failing_start]
        server = TigrCornServer(_http_ok_app, config)
        with self.assertRaisesRegex(RuntimeError, 'startup failed'):
            await server.start()
        self.assertFalse(server._started)
        await server.close()

    async def test_shutdown_hook_failures_are_suppressed_during_close(self) -> None:
        events: list[str] = []

        async def noisy_shutdown(_server) -> None:
            events.append('hook.shutdown')
            raise RuntimeError('ignore me')

        config = build_config(host='127.0.0.1', port=0, lifespan='off')
        config.hooks.on_shutdown = [noisy_shutdown]
        server = TigrCornServer(_http_ok_app, config)
        await server.start()
        await server.close()
        self.assertEqual(events, ['hook.shutdown'])


class Phase6ReloadHookContractTests(unittest.TestCase):
    def test_reload_hooks_run_before_child_restart_and_receive_config(self) -> None:
        events: list[str] = []
        config = build_config(app='tests.fixtures_pkg.appmod:app', host='127.0.0.1', port=8000)

        async def on_reload(reload_config) -> None:
            self.assertIs(reload_config, config)
            events.append('hook.reload')

        config.hooks.on_reload = [on_reload]
        reloader = PollingReloader([], config=config)

        with (
            mock.patch.object(PollingReloader, 'stop_child', autospec=True, side_effect=lambda _self: events.append('stop_child')),
            mock.patch.object(PollingReloader, 'spawn_child', autospec=True, side_effect=lambda _self: events.append('spawn_child')),
        ):
            reloader.restart_child()

        self.assertEqual(events, ['hook.reload', 'stop_child', 'spawn_child'])


class Phase6EmbeddedServerContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_embedded_server_is_a_first_class_documented_surface(self) -> None:
        config = build_config(host='127.0.0.1', port=0, lifespan='off')
        embedded = EmbeddedServer(_http_ok_app, config)

        await embedded.close()  # no-op before start
        first = await embedded.start()
        second = await embedded.start()
        self.assertIs(first, second)
        self.assertTrue(embedded.listeners)
        self.assertTrue(embedded.bound_endpoints())
        await embedded.close()

    def test_lifecycle_and_embedded_server_docs_exist(self) -> None:
        readme = Path('README.md').read_text(encoding='utf-8')
        contract = Path('docs/LIFECYCLE_AND_EMBEDDED_SERVER.md').read_text(encoding='utf-8')
        self.assertIn('docs/LIFECYCLE_AND_EMBEDDED_SERVER.md', readme)
        self.assertIn('on_startup', contract)
        self.assertIn('on_shutdown', contract)
        self.assertIn('on_reload', contract)
        self.assertIn('EmbeddedServer', contract)
        self.assertIn('lifespan.startup()', contract)
        self.assertIn('lifespan.shutdown()', contract)
        self.assertIn('Failure semantics', contract)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
