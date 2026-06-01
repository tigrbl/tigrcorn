from __future__ import annotations

from tigrcorn.contract import classify_binding, validate_binding_legality
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractRESTBindingClassificationTests(ContractClosureAssertions):
    def test_rest_binding_classification_contract(self) -> None:
        self.assert_binding_classification('rest')

    def test_rest_binding_shape_is_http_request_json_unary(self) -> None:
        classification = classify_binding("rest")
        self.assertEqual(classification.scope_type, "http")
        self.assertEqual(classification.family, "request")
        self.assertEqual(classification.exchange, "unary")
        self.assertEqual(classification.allowed_framings, ("json",))
        validate_binding_legality(binding="rest", family="request", subevent="request.body_in", exchange="unary")

    def test_rest_rejects_non_request_or_non_unary_shapes(self) -> None:
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="rest", family="stream", exchange="server_stream")
        with self.assertRaises(ConfigError):
            validate_binding_legality(binding="rest", family="request", exchange="duplex")
