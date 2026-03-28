from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RELEASE_ROOT = 'docs/review/conformance/releases/0.3.9/release-0.3.9/'
BOUNDARY_DOC = 'docs/review/conformance/CERTIFICATION_BOUNDARY.md'


class DocumentationReconciliationTests(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding='utf-8')

    def assertContainsAll(self, text: str, *needles: str) -> None:
        for needle in needles:
            self.assertIn(needle, text)

    def test_readme_references_canonical_boundary_release_root_and_current_state(self):
        text = self._read('README.md')
        self.assertContainsAll(
            text,
            BOUNDARY_DOC,
            CANONICAL_RELEASE_ROOT,
            'external_matrix.same_stack_replay.json',
            'external_matrix.release.json',
            'external_matrix.current_release.json',
            'certifiably fully RFC compliant under the authoritative certification boundary',
            'CURRENT_REPOSITORY_STATE.md',
        )

    def test_http3_quic_and_websocket_docs_reference_boundary_and_current_blockers(self):
        http3 = self._read('docs/protocols/http3.md')
        quic = self._read('docs/protocols/quic.md')
        websocket = self._read('docs/protocols/websocket.md')
        for text in (http3, quic, websocket):
            self.assertIn(BOUNDARY_DOC, text)
            self.assertIn(CANONICAL_RELEASE_ROOT, text)
        self.assertContainsAll(
            http3,
            'preserved passing third-party HTTP/3 request/response',
            'RFC 9220 scenarios',
            'package-owned TCP/TLS condition',
        )
        self.assertContainsAll(
            quic,
            'OpenSSL QUIC handshake',
            'preserves passing third-party HTTP/3 feature-axis scenarios',
            'package-wide RFC 8446 target is no longer blocked by the public TCP/TLS listener path',
        )
        self.assertContainsAll(
            websocket,
            'RFC 8441 WebSocket-over-HTTP/2',
            'RFC 9220 WebSocket-over-HTTP/3',
            'RFC 7692 across carriers',
        )

    def test_conformance_boundary_and_status_docs_are_aligned(self):
        boundary = self._read('docs/review/conformance/CERTIFICATION_BOUNDARY.md')
        conformance = self._read('docs/review/conformance/README.md')
        status = self._read('RFC_CERTIFICATION_STATUS.md')
        current = self._read('CURRENT_REPOSITORY_STATE.md')
        hardening = self._read('RFC_HARDENING_REPORT.md')
        for text in (boundary, conformance, status, current, hardening):
            self.assertIn(BOUNDARY_DOC, text)
        self.assertContainsAll(
            conformance,
            CANONICAL_RELEASE_ROOT,
            'certifiably fully RFC compliant under the authoritative certification boundary',
        )
        self.assertContainsAll(
            current,
            'certifiably fully RFC compliant',
            'evaluate_release_gates',
            'RFC 9220',
        )
        self.assertContainsAll(
            status,
            'certifiably fully RFC compliant',
            'independent-certification',
            'aioquic',
        )
        self.assertContainsAll(
            hardening,
            'preserved third-party `aioquic` HTTP/3 request/response artifacts',
            'package-owned TCP/TLS listener-path integration',
        )


if __name__ == '__main__':
    unittest.main()
