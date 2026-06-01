from __future__ import annotations

from tigrcorn.contract import classify_binding, validate_binding_legality
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractJSONRPCBindingClassificationTests(ContractClosureAssertions):
    def test_jsonrpc_binding_classification_contract(self) -> None:
        self.assert_binding_classification('jsonrpc')

    def test_jsonrpc_binding_shape_is_http_request_jsonrpc_unary(self) -> None:
        classification = classify_binding("json-rpc")
        self.assertEqual(classification.kind, "jsonrpc")
        self.assertEqual(classification.scope_type, "http")
        self.assertEqual(classification.family, "request")
        self.assertEqual(classification.exchange, "unary")
        self.assertEqual(classification.allowed_framings, ("jsonrpc",))
        validate_binding_legality(binding="json-rpc", family="request", subevent="request.body_in", exchange="unary")

    def test_jsonrpc_rejects_message_stream_or_json_substitution_shapes(self) -> None:
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="jsonrpc", family="message", exchange="duplex")
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="jsonrpc", family="stream", exchange="server_stream")
        self.assertNotIn("json", classify_binding("jsonrpc").allowed_framings)
