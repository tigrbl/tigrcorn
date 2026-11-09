from __future__ import annotations

from tigrcorn.contract import validate_scope
from tigrcorn.errors import ProtocolError

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractUnsupportedScopeRejectionTests(ContractClosureAssertions):
    def test_unsupported_scope_rejection_contract(self) -> None:
        self.assert_unsupported_scope_rejection()

    def test_rejects_non_mapping_missing_type_and_non_string_type(self) -> None:
        for scope in (None, [], {}, {"type": 3}):
            with self.subTest(scope=scope):
                with self.assertRaises(ProtocolError):
                    validate_scope(scope)  # type: ignore[arg-type]

    def test_rejects_malformed_webtransport_extension_metadata(self) -> None:
        for scope in (
            {"type": "webtransport", "path": "/wt", "extensions": []},
            {"type": "webtransport", "path": "/wt", "extensions": {"h3": {}, "quic": []}},
            {"type": "webtransport", "path": "/wt", "extensions": {"h3": []}},
        ):
            with self.subTest(scope=scope):
                with self.assertRaises(ProtocolError):
                    validate_scope(scope)
