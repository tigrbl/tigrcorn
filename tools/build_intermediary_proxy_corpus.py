from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "docs/review/conformance/intermediary_proxy_corpus"
INDEPENDENT_ROOT = ROOT / "docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-independent-certification-release-matrix"
CORPUS_PATH = ROOT / "docs/review/conformance/corpus.json"


@dataclass(frozen=True)
class CorpusCase:
    corpus_id: str
    source_kind: str
    source_ref: str
    carrier: str
    peer: str
    note: str


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding='utf-8')


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> int:
    if CORPUS_ROOT.exists():
        shutil.rmtree(CORPUS_ROOT)
    (CORPUS_ROOT / 'cases').mkdir(parents=True)
    vectors = {item['name']: item for item in _load_json(CORPUS_PATH).get('vectors', [])}
    cases = [
        CorpusCase(
            'http11-curl-origin-form-post',
            'independent_artifact',
            'http1-server-curl-client',
            'http1.1',
            'curl',
            'Third-party preserved HTTP/1.1 artifact that seeds the intermediary/proxy corpus with real on-the-wire request/response evidence.',
        ),
        CorpusCase(
            'http11-connect-relay-local-vector',
            'local_vector',
            'http-connect-relay',
            'http1.1',
            'tigrcorn-fixture',
            'Local CONNECT relay vector preserved until broader third-party intermediary/proxy artifacts are captured.',
        ),
        CorpusCase(
            'http2-connect-relay-local-vector',
            'local_vector',
            'http-connect-relay',
            'http2',
            'tigrcorn-fixture',
            'Local CONNECT relay vector preserved for the HTTP/2 carrier pending broader third-party intermediary/proxy artifacts.',
        ),
        CorpusCase(
            'http3-connect-relay-local-vector',
            'local_vector',
            'http-connect-relay',
            'http3',
            'tigrcorn-fixture',
            'Local CONNECT relay vector preserved for the HTTP/3 carrier pending broader third-party intermediary/proxy artifacts.',
        ),
    ]
    index_cases = []
    for item in cases:
        case_dir = CORPUS_ROOT / 'cases' / item.corpus_id
        case_dir.mkdir(parents=True, exist_ok=True)
        if item.source_kind == 'independent_artifact':
            src = INDEPENDENT_ROOT / item.source_ref
            if not src.exists():
                raise SystemExit(f'missing source artifact directory: {src}')
            for entry in src.iterdir():
                if entry.is_dir():
                    shutil.copytree(entry, case_dir / entry.name)
                else:
                    shutil.copy2(entry, case_dir / entry.name)
            _write_json(case_dir / 'corpus_metadata.json', {
                'corpus_id': item.corpus_id,
                'source_kind': item.source_kind,
                'source_ref': item.source_ref,
                'carrier': item.carrier,
                'peer': item.peer,
                'note': item.note,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'corpus_entry_kind': 'seed_third_party_http11',
                'artifact_dir': _rel(case_dir),
            })
        else:
            vector = vectors[item.source_ref]
            _write_json(case_dir / 'source_local_vector.json', vector)
            _write_json(case_dir / 'corpus_metadata.json', {
                'corpus_id': item.corpus_id,
                'source_kind': item.source_kind,
                'source_ref': item.source_ref,
                'carrier': item.carrier,
                'peer': item.peer,
                'note': item.note,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'corpus_entry_kind': 'local_proxy_vector',
                'artifact_dir': _rel(case_dir),
            })
        index_cases.append({
            'id': item.corpus_id,
            'source_kind': item.source_kind,
            'source_ref': item.source_ref,
            'carrier': item.carrier,
            'peer': item.peer,
            'artifact_dir': _rel(case_dir),
        })

    _write_json(CORPUS_ROOT / 'index.json', {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'corpus_root': _rel(CORPUS_ROOT),
        'cases': index_cases,
        'seed_kind': 'intermediary_proxy_corpus',
        'scope_note': 'This corpus improves repository transparency for intermediary/proxy-style behavior, but it is not itself an RFC certification bundle.',
        'independent_matrix_sha256': sha256((INDEPENDENT_ROOT / 'index.json').read_bytes()).hexdigest() if (INDEPENDENT_ROOT / 'index.json').exists() else None,
    })
    (CORPUS_ROOT / 'README.md').write_text(
        '# Intermediary / proxy corpus\n\n'
        'This seed corpus collects the currently preserved HTTP/1.1 third-party artifact plus carrier-specific CONNECT relay vector metadata.\n'
        'It improves repository transparency for intermediary/proxy-style behavior, but it does not replace broader third-party proxy interoperability evidence.\n',
        encoding='utf-8',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
