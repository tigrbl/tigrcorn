from __future__ import annotations

from tigrcorn.contract import require_lossless_metadata
from tigrcorn.errors import ProtocolError

from tests.contract_closure_assertions import ContractClosureAssertions


class ContractLossyMetadataRejectionTests(ContractClosureAssertions):
    def test_lossy_metadata_rejection_contract(self) -> None:
        self.assert_lossy_metadata_rejection()

    def test_rejects_whitespace_empty_bytes_and_nested_loss(self) -> None:
        for value in ("   ", b"", {"connection_id": ""}, ["ok", None]):
            with self.subTest(value=value):
                with self.assertRaises(ProtocolError):
                    require_lossless_metadata("transport", value)

    def test_accepts_nested_lossless_metadata(self) -> None:
        payload = {"connection_id": "c1", "stream": {"stream_id": "s1"}, "labels": ["tls", "h2"]}
        self.assertIs(require_lossless_metadata("transport", payload), payload)
