from __future__ import annotations

from tigrcorn.config.load import build_config, config_from_mapping
from tigrcorn.contract import classify_binding, product_surface_status
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class RESTRuntimeExclusionTests(ContractClosureAssertions):
    def test_rest_runtime_exclusion_contract(self) -> None:
        self.assert_runtime_exclusion('rest')

    def test_rest_is_classification_only_not_app_interface(self) -> None:
        classification = classify_binding("rest")
        self.assertFalse(classification.runtime_owned)
        self.assertTrue(classification.classification_only)
        self.assertEqual(classification.dispatch_runtime, "application")
        self.assertFalse(product_surface_status("rest").runtime_available)

    def test_rest_app_interface_and_listener_protocol_fail_closed(self) -> None:
        with self.assertRaises(ConfigError):
            config_from_mapping({"app": {"interface": "rest"}})
        with self.assertRaises(ConfigError):
            build_config(protocols=["rest"], host="127.0.0.1", port=0)
