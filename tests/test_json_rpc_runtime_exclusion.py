from __future__ import annotations

from tigrcorn.config.load import build_config, config_from_mapping
from tigrcorn.contract import classify_binding, product_surface_excluded, product_surface_status, require_product_boundary_exclusion
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class JSONRPCRuntimeExclusionTests(ContractClosureAssertions):
    def test_json_rpc_runtime_exclusion_contract(self) -> None:
        self.assert_runtime_exclusion('json-rpc')

    def test_jsonrpc_is_classification_only_not_app_interface(self) -> None:
        classification = classify_binding("jsonrpc")
        self.assertFalse(classification.runtime_owned)
        self.assertTrue(classification.classification_only)
        self.assertEqual(classification.dispatch_runtime, "application")
        self.assertFalse(product_surface_status("json_rpc").runtime_available)

    def test_jsonrpc_is_explicit_classification_only_boundary_exclusion(self) -> None:
        status = require_product_boundary_exclusion("json-rpc")
        self.assertTrue(product_surface_excluded("json_rpc"))
        self.assertTrue(status.classification_only)
        self.assertFalse(status.compatibility_exclusion)

    def test_jsonrpc_app_interface_and_listener_protocol_fail_closed(self) -> None:
        with self.assertRaises(ConfigError):
            config_from_mapping({"app": {"interface": "jsonrpc"}})
        with self.assertRaises(ConfigError):
            build_config(protocols=["jsonrpc"], host="127.0.0.1", port=0)
