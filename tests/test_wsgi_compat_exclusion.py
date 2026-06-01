from __future__ import annotations

from tigrcorn.app_interfaces import AppInterfaceError, resolve_app_dispatch
from tigrcorn.config.load import config_from_mapping
from tigrcorn.errors import ConfigError

from tests.contract_closure_assertions import ContractClosureAssertions


class WSGICompatExclusionTests(ContractClosureAssertions):
    def test_wsgi_compat_exclusion_contract(self) -> None:
        self.assert_compat_exclusion('wsgi')

    def test_wsgi_app_interface_is_rejected_by_config(self) -> None:
        with self.assertRaises(ConfigError):
            config_from_mapping({"app": {"interface": "wsgi"}})

    def test_wsgi_callable_shape_is_not_auto_accepted(self) -> None:
        def wsgi(environ, start_response):
            start_response("200 OK", [])
            return [b"ok"]

        with self.assertRaises(AppInterfaceError):
            resolve_app_dispatch(wsgi, "auto")
