import asyncio
import unittest

from tigrcorn.asgi.scopes.websocket import build_websocket_scope
from tigrcorn.protocols.http1.parser import ParsedRequest
from tigrcorn.protocols.websocket.handler import _WSAppSend


class _FakeWriter:
    def write(self, data: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None


class WebSocketRFC7936Tests(unittest.IsolatedAsyncioTestCase):
    def test_scope_preserves_subprotocol_case(self):
        request = ParsedRequest(
            method="GET",
            target="/ws",
            path="/ws",
            raw_path=b"/ws",
            query_string=b"",
            http_version="1.1",
            headers=[(b"sec-websocket-protocol", b"chat, Chat, superchat")],
            body=b"",
            keep_alive=True,
            expect_continue=False,
            websocket_upgrade=True,
        )

        scope = build_websocket_scope(
            request,
            client=("127.0.0.1", 50000),
            server=("127.0.0.1", 8000),
            scheme="ws",
        )

        self.assertEqual(scope["subprotocols"], ["chat", "Chat", "superchat"])

    async def test_accept_subprotocol_match_is_case_sensitive(self):
        sender = _WSAppSend(
            writer=_FakeWriter(),
            server_header=None,
            state={
                "accepted": False,
                "closed": False,
                "http_denied": False,
                "http_denial_status": 403,
                "http_denial_headers": [],
                "http_denial_started": False,
                "sec_websocket_key": b"dGhlIHNhbXBsZSBub25jZQ==",
                "request_headers": [(b"sec-websocket-protocol", b"chat")],
                "permessage_deflate_offers": [],
                "permessage_deflate_runtime": None,
            },
            accepted=asyncio.Event(),
            allowed_subprotocols=["chat"],
        )

        with self.assertRaises(RuntimeError):
            await sender({"type": "websocket.accept", "subprotocol": "Chat", "headers": []})
