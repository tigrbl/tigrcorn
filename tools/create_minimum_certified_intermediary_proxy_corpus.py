
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6/release-0.3.6'
INDEPENDENT_ROOT = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix'
CORPUS_ROOT = ROOT / 'docs/review/conformance/intermediary_proxy_corpus_minimum_certified'
CORPUS_PATH = ROOT / 'docs/review/conformance/corpus.json'
EXTERNAL_RELEASE = ROOT / 'docs/review/conformance/external_matrix.release.json'

INDEPENDENT_CASES = [
  {
    "corpus_id": "http11-curl-origin-form-post-certified",
    "source_ref": "http1-server-curl-client",
    "carrier": "http1.1",
    "peer": "curl",
    "scope": [
      "origin-form",
      "request-forwarding",
      "header-forwarding"
    ],
    "note": "Minimum certified HTTP/1.1 request-forwarding and origin-form evidence preserved from the third-party curl artifact."
  },
  {
    "corpus_id": "http2-h2-origin-form-post-certified",
    "source_ref": "http2-server-h2-client",
    "carrier": "http2",
    "peer": "h2",
    "scope": [
      "request-forwarding",
      "header-forwarding",
      "persistent-carrier-baseline"
    ],
    "note": "Minimum certified HTTP/2 forwarding semantics preserved from the third-party h2 client artifact."
  },
  {
    "corpus_id": "http3-aioquic-origin-form-post-certified",
    "source_ref": "http3-server-aioquic-client-post",
    "carrier": "http3",
    "peer": "aioquic",
    "scope": [
      "request-forwarding",
      "header-forwarding",
      "persistent-carrier-baseline"
    ],
    "note": "Minimum certified HTTP/3 forwarding semantics preserved from the third-party aioquic client artifact."
  }
]
SUPPLEMENTAL_VECTORS = [
  [
    "http11-connect-relay-local-vector",
    "http1.1",
    "http-connect-relay"
  ],
  [
    "http2-connect-relay-local-vector",
    "http2",
    "http-connect-relay"
  ],
  [
    "http3-connect-relay-local-vector",
    "http3",
    "http-connect-relay"
  ],
  [
    "http11-trailer-fields-local-vector",
    "http1.1",
    "http-trailer-fields"
  ],
  [
    "http2-trailer-fields-local-vector",
    "http2",
    "http-trailer-fields"
  ],
  [
    "http3-trailer-fields-local-vector",
    "http3",
    "http-trailer-fields"
  ],
  [
    "http11-content-coding-local-vector",
    "http1.1",
    "http-content-coding"
  ],
  [
    "http2-content-coding-local-vector",
    "http2",
    "http-content-coding"
  ],
  [
    "http3-content-coding-local-vector",
    "http3",
    "http-content-coding"
  ]
]

def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))

def main() -> int:
    vectors = {v['name']: v for v in _load_json(CORPUS_PATH).get('vectors', [])}
    release_scenarios = {s['id']: s for s in _load_json(EXTERNAL_RELEASE)['scenarios']}
    if CORPUS_ROOT.exists():
        shutil.rmtree(CORPUS_ROOT)
    (CORPUS_ROOT / 'cases').mkdir(parents=True)
    index_cases = []
    matrix_scenarios = []
    for item in INDEPENDENT_CASES:
        src_dir = INDEPENDENT_ROOT / item['source_ref']
        dst_dir = CORPUS_ROOT / 'cases' / item['corpus_id']
        shutil.copytree(src_dir, dst_dir)
        result = _load_json(dst_dir / 'result.json')
        result['artifact_dir'] = _rel(dst_dir)
        if isinstance(result.get('artifacts'), dict):
            for entry in result['artifacts'].values():
                if isinstance(entry, dict) and entry.get('path'):
                    entry['path'] = _rel(dst_dir / Path(entry['path']).name)
        _write_json(dst_dir / 'result.json', result)
        _write_json(dst_dir / 'corpus_metadata.json', {
            'artifact_dir': _rel(dst_dir),
            'carrier': item['carrier'],
            'corpus_entry_kind': 'minimum_certified_independent_intermediary_case',
            'corpus_id': item['corpus_id'],
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'minimum_certified': True,
            'note': item['note'],
            'peer': item['peer'],
            'scope': item['scope'],
            'source_kind': 'independent_artifact',
            'source_ref': item['source_ref'],
        })
        index_cases.append({
            'id': item['corpus_id'],
            'carrier': item['carrier'],
            'peer': item['peer'],
            'artifact_dir': _rel(dst_dir),
            'source_kind': 'independent_artifact',
            'source_ref': item['source_ref'],
            'minimum_certified': True,
            'scope': item['scope'],
        })
        clone = json.loads(json.dumps(release_scenarios[item['source_ref']]))
        clone['id'] = item['corpus_id']
        clone['feature'] = 'intermediary-proxy-minimum-certified'
        clone['metadata']['matrix_kind'] = 'minimum-certified-intermediary-proxy'
        clone['metadata']['intermediary_proxy_scope'] = item['scope']
        clone['metadata']['source_independent_scenario'] = item['source_ref']
        matrix_scenarios.append(clone)
    for case_id, carrier, vector_name in SUPPLEMENTAL_VECTORS:
        dst_dir = CORPUS_ROOT / 'cases' / case_id
        dst_dir.mkdir(parents=True, exist_ok=True)
        _write_json(dst_dir / 'source_local_vector.json', vectors[vector_name])
        _write_json(dst_dir / 'corpus_metadata.json', {
            'artifact_dir': _rel(dst_dir),
            'carrier': carrier,
            'corpus_entry_kind': 'supplemental_local_vector',
            'corpus_id': case_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'minimum_certified': False,
            'note': 'Supplemental local vector retained in the minimum certified corpus until broader third-party intermediary/proxy captures are preserved for this semantic area.',
            'peer': 'tigrcorn-fixture',
            'scope': [vector_name],
            'source_kind': 'local_vector',
            'source_ref': vector_name,
        })
        index_cases.append({
            'id': case_id,
            'carrier': carrier,
            'peer': 'tigrcorn-fixture',
            'artifact_dir': _rel(dst_dir),
            'source_kind': 'local_vector',
            'source_ref': vector_name,
            'minimum_certified': False,
            'scope': [vector_name],
        })
    _write_json(CORPUS_ROOT / 'index.json', {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'corpus_root': _rel(CORPUS_ROOT),
        'corpus_kind': 'minimum_certified_intermediary_proxy_corpus',
        'scope_note': 'This corpus promotes one preserved third-party forwarding artifact per applicable carrier into a minimum certified intermediary/proxy-adjacent corpus while retaining local vector supplements for CONNECT, trailers, and content-coding semantics pending broader third-party proxy captures.',
        'cases': index_cases,
        'minimum_certified_case_count': len(INDEPENDENT_CASES),
        'supplemental_case_count': len(SUPPLEMENTAL_VECTORS),
        'source_independent_bundle_sha256': sha256((INDEPENDENT_ROOT / 'index.json').read_bytes()).hexdigest(),
    })
    _write_json(CORPUS_ROOT / 'manifest.json', {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'corpus_root': _rel(CORPUS_ROOT),
        'corpus_kind': 'minimum_certified_intermediary_proxy_corpus',
        'minimum_certified_case_ids': [c['corpus_id'] for c in INDEPENDENT_CASES],
        'supplemental_case_ids': [cid for cid, _, _ in SUPPLEMENTAL_VECTORS],
        'scope_note': 'Minimum certified intermediary/proxy corpus for carrier-preserving forwarding semantics. This is not yet a full multi-hop intermediary certification program.',
    })
    (CORPUS_ROOT / 'README.md').write_text(
        '# Minimum certified intermediary / proxy corpus\n\n'
        'This corpus promotes one preserved third-party forwarding artifact per applicable carrier into a minimum certified intermediary/proxy-adjacent evidence root.\n\n'
        'Included minimum certified cases:\n\n'
        '- HTTP/1.1 origin-form / request-forwarding via curl\n'
        '- HTTP/2 forwarding semantics via h2\n'
        '- HTTP/3 forwarding semantics via aioquic\n\n'
        'Supplemental local-vector cases remain in-tree for CONNECT, trailers, and content-coding semantics until broader third-party proxy captures are preserved.\n',
        encoding='utf-8'
    )
    _write_json(ROOT / 'docs/review/conformance/external_matrix.intermediary_proxy.minimum.json', {
        'name': 'tigrcorn-minimum-certified-intermediary-proxy',
        'metadata': {
            'matrix_kind': 'minimum-certified-intermediary-proxy',
            'bundle_root': _rel(CORPUS_ROOT),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'scope_note': 'Reference matrix for the minimum certified intermediary/proxy-adjacent corpus promoted in Phase 5.',
        },
        'scenarios': matrix_scenarios,
    })
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
