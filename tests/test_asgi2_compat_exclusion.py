from __future__ import annotations

from tigrcorn.app_interfaces import AppInterfaceError, resolve_app_dispatch
from tigrcorn.config.load import config_from_mapping
from tigrcorn.contract import product_surface_excluded, require_product_boundary_exclusion
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class ASGI2CompatExclusionTests(ContractClosureAssertions):
    def test_asgi2_compat_exclusion_contract(self) -> None:
        self.assert_compat_exclusion('asgi2')

    def test_asgi2_app_interface_is_rejected_by_config(self) -> None:
        with self.assertRaises(ConfigError):
            config_from_mapping({"app": {"interface": "asgi2"}})

    def test_asgi2_is_explicit_product_boundary_exclusion(self) -> None:
        status = require_product_boundary_exclusion("asgi2")
        self.assertTrue(product_surface_excluded("asgi2"))
        self.assertTrue(status.compatibility_exclusion)
        self.assertFalse(status.classification_only)

    def test_asgi2_callable_shape_is_not_auto_accepted(self) -> None:
        def asgi2(scope, receive):
            async def app(send):
                return None

            return app

        with self.assertRaises(AppInterfaceError):
            resolve_app_dispatch(asgi2, "auto")
