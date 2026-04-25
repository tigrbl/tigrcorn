from __future__ import annotations

from tests.contract_closure_assertions import ContractClosureAssertions


class TigrASGIContractValidationTests(ContractClosureAssertions):
    def test_tigr_asgi_contract_validation_surface(self) -> None:
        self.assert_contract_validation_surface()
