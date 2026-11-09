from __future__ import annotations

from tigrcorn.contract import endpoint_metadata
from tigrcorn.errors import ProtocolError

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractInvalidEndpointMetadataRejectionTests(ContractClosureAssertions):
    def test_invalid_endpoint_metadata_rejection_contract(self) -> None:
        self.assert_invalid_endpoint_metadata_rejection()

    def test_rejects_invalid_tcp_port_and_fd_values(self) -> None:
        for payload in (
            {"kind": "tcp", "address": "127.0.0.1", "port": -1},
            {"kind": "tcp", "address": "127.0.0.1", "port": 70_000},
            {"kind": "tcp", "address": "127.0.0.1", "port": "443"},
            {"kind": "fd", "fd": -1},
            {"kind": "fd", "fd": "3"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ProtocolError):
                    endpoint_metadata(**payload)

    def test_rejects_unknown_or_wrong_family_endpoint_fields(self) -> None:
        with self.assertRaises(ProtocolError):
            endpoint_metadata("tcp", address="127.0.0.1", port=443, unexpected=True)
        with self.assertRaises(ProtocolError):
            endpoint_metadata("pipe", address="not-a-pipe")
