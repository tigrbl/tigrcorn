from __future__ import annotations

from tigrcorn.contract import classify_binding, validate_binding_legality
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractSSEBindingClassificationTests(ContractClosureAssertions):
    def test_sse_binding_classification_contract(self) -> None:
        self.assert_binding_classification('sse')

    def test_sse_binding_shape_is_http_stream_sse_server_stream(self) -> None:
        classification = classify_binding("sse")
        self.assertEqual(classification.scope_type, "http")
        self.assertEqual(classification.family, "stream")
        self.assertEqual(classification.exchange, "server_stream")
        self.assertEqual(classification.allowed_framings, ("sse",))
        validate_binding_legality(binding="sse", family="stream", subevent="stream.chunk_out", exchange="server_stream")

    def test_sse_rejects_request_message_or_duplex_shapes(self) -> None:
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="sse", family="request", exchange="unary")
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="sse", family="message", exchange="server_stream")
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="sse", family="stream", exchange="duplex")
