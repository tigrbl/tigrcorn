from __future__ import annotations

from tigrcorn.config.load import config_from_mapping
from tigrcorn.contract import product_surface_excluded, require_product_boundary_exclusion
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class RSGICompatExclusionTests(ContractClosureAssertions):
    def test_rsgi_compat_exclusion_contract(self) -> None:
        self.assert_compat_exclusion('rsgi')

    def test_rsgi_app_interface_is_rejected_by_config(self) -> None:
        with self.assertRaises(ConfigError):
            config_from_mapping({"app": {"interface": "rsgi"}})

    def test_rsgi_is_explicit_product_boundary_exclusion(self) -> None:
        status = require_product_boundary_exclusion("rsgi")
        self.assertTrue(product_surface_excluded("rsgi"))
        self.assertTrue(status.compatibility_exclusion)
        self.assertFalse(status.classification_only)
