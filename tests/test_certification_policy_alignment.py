from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC = 'docs/review/conformance/CERTIFICATION_BOUNDARY.md'
BOUNDARY_JSON = 'docs/review/conformance/certification_boundary.json'
POLICY_DOC = 'docs/review/conformance/CERTIFICATION_POLICY_ALIGNMENT.md'


class CertificationPolicyAlignmentTests(unittest.TestCase):
    def test_boundary_claim_is_per_rfc_and_authoritative(self):
        payload = json.loads((ROOT / BOUNDARY_JSON).read_text(encoding='utf-8'))
        claim = payload['claim']
        self.assertIn('required evidence tier declared per RFC', claim)

    def test_policy_docs_name_local_tier_rfcs_explicitly(self):
        text = (ROOT / POLICY_DOC).read_text(encoding='utf-8')
        self.assertIn(BOUNDARY_DOC, text)
        for needle in ('RFC 7692', 'RFC 9110 §9.3.6', 'RFC 9110 §6.5', 'RFC 9110 §8', 'RFC 6960'):
            self.assertIn(needle, text)
        self.assertIn('certifiably fully RFC compliant', text)


if __name__ == '__main__':
    unittest.main()
