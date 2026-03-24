import unittest

from tigrcorn.protocols.websocket.extensions import (
    PerMessageDeflateAgreement,
    PerMessageDeflateRuntime,
    default_permessage_deflate_agreement,
    negotiate_permessage_deflate,
    parse_permessage_deflate_offers,
)


class WebSocketRFC7692Tests(unittest.TestCase):
    def test_server_may_request_client_no_context_takeover_without_offer_hint(self):
        agreement = negotiate_permessage_deflate(
            request_headers=[(b'sec-websocket-extensions', b'permessage-deflate')],
            response_headers=[(b'sec-websocket-extensions', b'permessage-deflate; client_no_context_takeover; server_max_window_bits=10')],
        )
        self.assertEqual(
            agreement,
            PerMessageDeflateAgreement(
                client_no_context_takeover=True,
                server_max_window_bits=10,
            ),
        )

    def test_server_must_not_set_client_max_window_bits_without_client_offer(self):
        with self.assertRaises(RuntimeError):
            negotiate_permessage_deflate(
                request_headers=[(b'sec-websocket-extensions', b'permessage-deflate')],
                response_headers=[(b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits=10')],
            )

    def test_context_takeover_reduces_second_message_size(self):
        payload = b'HelloHelloHelloHelloHello'
        sender = PerMessageDeflateRuntime(PerMessageDeflateAgreement())
        receiver = PerMessageDeflateRuntime(PerMessageDeflateAgreement())

        first = sender.compress_message(payload)
        second = sender.compress_message(payload)
        self.assertLess(len(second), len(first))
        self.assertEqual(receiver.decompress_message(first), payload)
        self.assertEqual(receiver.decompress_message(second), payload)

    def test_no_context_takeover_restarts_compression_and_decompression_state(self):
        payload = b'HelloHelloHelloHelloHello'
        agreement = PerMessageDeflateAgreement(
            server_no_context_takeover=True,
            client_no_context_takeover=True,
            server_max_window_bits=10,
            client_max_window_bits=10,
        )
        sender = PerMessageDeflateRuntime(agreement)
        receiver = PerMessageDeflateRuntime(agreement)

        first = sender.compress_message(payload)
        second = sender.compress_message(payload)
        self.assertEqual(first, second)
        self.assertEqual(receiver.decompress_message(first), payload)
        self.assertEqual(receiver.decompress_message(second), payload)

    def test_default_agreement_mirrors_explicit_window_bits(self):
        offers = parse_permessage_deflate_offers([
            (b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits=15; server_max_window_bits=15'),
        ])
        agreement = default_permessage_deflate_agreement(offers)
        self.assertEqual(
            agreement,
            PerMessageDeflateAgreement(server_max_window_bits=15, client_max_window_bits=15),
        )

    def test_negotiate_permessage_deflate_with_explicit_window_bits(self):
        agreement = negotiate_permessage_deflate(
            request_headers=[(b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits=15; server_max_window_bits=15')],
            response_headers=[(b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits=15; server_max_window_bits=15')],
        )
        self.assertEqual(
            agreement,
            PerMessageDeflateAgreement(server_max_window_bits=15, client_max_window_bits=15),
        )

