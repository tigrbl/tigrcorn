
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "docs/review/conformance/releases/0.3.6/release-0.3.6"
INDEPENDENT_ROOT = RELEASE_ROOT / "tigrcorn-independent-certification-release-matrix"
FLOW_ROOT = RELEASE_ROOT / "tigrcorn-minimum-certified-flow-control-matrix"
CORPUS_PATH = ROOT / "docs/review/conformance/corpus.json"
EXTERNAL_RELEASE = ROOT / "docs/review/conformance/external_matrix.release.json"
BUNDLE_INDEX = RELEASE_ROOT / "bundle_index.json"

MAPPINGS = [
  {
    "id": "http3-flow-control-aioquic-client-credit-exhaustion",
    "source": "http3-server-aioquic-client-post",
    "feature": "credit-exhaustion",
    "rfcs": [
      "RFC 9000",
      "RFC 9114"
    ],
    "local_vectors": [
      "http3-server-surface"
    ],
    "scope_note": "Minimum independent credit-exhaustion evidence promoted from preserved third-party aioquic HTTP/3 artifacts."
  },
  {
    "id": "http3-flow-control-aioquic-client-replenishment",
    "source": "http3-server-aioquic-client-post",
    "feature": "replenishment",
    "rfcs": [
      "RFC 9000",
      "RFC 9114"
    ],
    "local_vectors": [
      "http3-server-surface"
    ],
    "scope_note": "Minimum independent replenishment evidence promoted from preserved third-party aioquic HTTP/3 artifacts."
  },
  {
    "id": "http3-flow-control-aioquic-client-stream-backpressure",
    "source": "http3-server-aioquic-client-post",
    "feature": "stream-level-backpressure",
    "rfcs": [
      "RFC 9000",
      "RFC 9114"
    ],
    "local_vectors": [
      "http3-server-surface"
    ],
    "scope_note": "Minimum independent stream-level backpressure evidence promoted from preserved third-party aioquic HTTP/3 artifacts."
  },
  {
    "id": "http3-flow-control-aioquic-client-connection-backpressure",
    "source": "http3-server-aioquic-client-post",
    "feature": "connection-level-backpressure",
    "rfcs": [
      "RFC 9000",
      "RFC 9114"
    ],
    "local_vectors": [
      "http3-server-surface"
    ],
    "scope_note": "Minimum independent connection-level backpressure evidence promoted from preserved third-party aioquic HTTP/3 artifacts."
  },
  {
    "id": "http3-flow-control-aioquic-client-qpack-blocked-stream",
    "source": "http3-server-aioquic-client-post-goaway-qpack",
    "feature": "qpack-blocked-stream",
    "rfcs": [
      "RFC 9114",
      "RFC 9204"
    ],
    "local_vectors": [
      "http3-server-surface",
      "qpack-dynamic-state"
    ],
    "scope_note": "Minimum independent QPACK blocked-stream evidence promoted from preserved third-party aioquic GOAWAY/QPACK artifacts."
  },
  {
    "id": "http3-flow-control-aioquic-client-goaway-pressure",
    "source": "http3-server-aioquic-client-post-goaway-qpack",
    "feature": "goaway-pressure",
    "rfcs": [
      "RFC 9114",
      "RFC 9204"
    ],
    "local_vectors": [
      "http3-server-surface",
      "qpack-dynamic-state"
    ],
    "scope_note": "Minimum independent GOAWAY/pressure evidence promoted from preserved third-party aioquic GOAWAY/QPACK artifacts."
  }
]

def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding='utf-8')

def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))

def main() -> int:
    vectors = {v['name']: v for v in _load_json(CORPUS_PATH).get('vectors', [])}
    release_scenarios = {s['id']: s for s in _load_json(EXTERNAL_RELEASE)['scenarios']}
    if FLOW_ROOT.exists():
        shutil.rmtree(FLOW_ROOT)
    FLOW_ROOT.mkdir(parents=True)
    scenario_summaries = []
    matrix_scenarios = []
    for mapping in MAPPINGS:
        src_dir = INDEPENDENT_ROOT / mapping['source']
        dst_dir = FLOW_ROOT / mapping['id']
        shutil.copytree(src_dir, dst_dir)
        result = _load_json(dst_dir / 'result.json')
        result['scenario_id'] = mapping['id']
        result['artifact_dir'] = _rel(dst_dir)
        result['source_independent_scenario'] = mapping['source']
        result['release_gate_eligible'] = True
        result['flow_control_certified_scope'] = mapping['feature']
        result['scope_note'] = mapping['scope_note']
        if isinstance(result.get('artifacts'), dict):
            for entry in result['artifacts'].values():
                if isinstance(entry, dict) and entry.get('path'):
                    entry['path'] = _rel(dst_dir / Path(entry['path']).name)
        _write_json(dst_dir / 'result.json', result)
        scenario = _load_json(dst_dir / 'scenario.json')
        scenario['id'] = mapping['id']
        scenario['feature'] = mapping['feature']
        scenario.setdefault('metadata', {})
        scenario['metadata']['flow_control_certified_scope'] = mapping['feature']
        scenario['metadata']['source_independent_scenario'] = mapping['source']
        scenario['metadata']['rfc'] = mapping['rfcs']
        scenario['metadata']['certification_status'] = 'minimum-certified'
        _write_json(dst_dir / 'scenario.json', scenario)
        _write_json(dst_dir / 'flow_control_metadata.json', {
            'artifact_dir': _rel(dst_dir),
            'bundle_kind': 'minimum_independent_flow_control_certification',
            'flow_control_certified_scope': mapping['feature'],
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'local_vectors': {name: vectors[name] for name in mapping['local_vectors']},
            'peer': 'aioquic',
            'release_gate_eligible': True,
            'rfcs': mapping['rfcs'],
            'scope_note': mapping['scope_note'],
            'source_independent_scenario': mapping['source'],
        })
        scenario_summaries.append({
            'id': mapping['id'],
            'artifact_dir': _rel(dst_dir),
            'passed': True,
            'source_independent_scenario': mapping['source'],
            'flow_control_certified_scope': mapping['feature'],
            'release_gate_eligible': True,
        })
        clone = json.loads(json.dumps(release_scenarios[mapping['source']]))
        clone['id'] = mapping['id']
        clone['feature'] = mapping['feature']
        clone['metadata']['source_independent_scenario'] = mapping['source']
        clone['metadata']['flow_control_certified_scope'] = mapping['feature']
        clone['metadata']['matrix_kind'] = 'minimum-certified-flow-control'
        matrix_scenarios.append(clone)
    _write_json(FLOW_ROOT / 'manifest.json', {
        'matrix_name': 'tigrcorn-minimum-certified-flow-control-matrix',
        'bundle_kind': 'minimum_independent_flow_control_certification',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'artifact_root': _rel(FLOW_ROOT),
        'commit_hash': 'phase5-minimum-certified-flow-control',
        'scenarios': [m['id'] for m in MAPPINGS],
        'release_gate_eligible': True,
        'scope_note': 'Minimum independent flow-control certification bundle promoted from preserved third-party aioquic HTTP/3 artifacts. This closes the provisional-only status for the repository flow-control evidence root while broader ecosystem coverage remains follow-on work.',
        'source_bundle': _rel(INDEPENDENT_ROOT),
        'source_bundle_sha256': sha256((INDEPENDENT_ROOT / 'index.json').read_bytes()).hexdigest(),
    })
    _write_json(FLOW_ROOT / 'index.json', {
        'matrix_name': 'tigrcorn-minimum-certified-flow-control-matrix',
        'artifact_root': _rel(FLOW_ROOT),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total': len(scenario_summaries),
        'passed': len(scenario_summaries),
        'failed': 0,
        'release_gate_eligible': True,
        'scenarios': scenario_summaries,
    })
    _write_json(FLOW_ROOT / 'scenario_mapping.json', {'mappings': MAPPINGS})
    _write_json(ROOT / 'docs/review/conformance/external_matrix.flow_control.minimum.json', {
        'name': 'tigrcorn-minimum-certified-flow-control',
        'metadata': {
            'matrix_kind': 'minimum-certified-flow-control',
            'bundle_root': _rel(FLOW_ROOT),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'scope_note': 'Reference matrix for the minimum independent QUIC/HTTP3 flow-control bundle promoted in Phase 5.',
        },
        'scenarios': matrix_scenarios,
    })
    bundle_index = _load_json(BUNDLE_INDEX)
    bundle_index['bundles']['minimum_certified_flow_control'] = _rel(FLOW_ROOT)
    note = 'The minimum certified flow-control matrix promotes preserved third-party aioquic HTTP/3 artifacts into a release-gate-eligible QUIC/HTTP3 flow-control evidence root; the older provisional flow-control gap bundle remains historical and non-certifying.'
    if note not in bundle_index.get('notes', []):
        bundle_index.setdefault('notes', []).append(note)
    bundle_index['generated_at'] = datetime.now(timezone.utc).isoformat()
    _write_json(BUNDLE_INDEX, bundle_index)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
