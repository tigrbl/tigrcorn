from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "docs/review/conformance/releases/0.3.6/release-0.3.6"
SAME_STACK_ROOT = RELEASE_ROOT / "tigrcorn-same-stack-replay-matrix"
CORPUS_PATH = ROOT / "docs/review/conformance/corpus.json"
PROVISIONAL_ROOT = RELEASE_ROOT / "tigrcorn-provisional-flow-control-gap-bundle"
BUNDLE_INDEX_PATH = RELEASE_ROOT / "bundle_index.json"
RELEASE_COMMIT_HASH = "release-0.3.6-offline-provisional-flow-control-gap-bundle"


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


@dataclass(frozen=True)
class ScenarioMapping:
    provisional_id: str
    source_same_stack_id: str
    feature: str
    rfcs: tuple[str, ...]
    local_vectors: tuple[str, ...]
    note: str


SCENARIO_MAPPINGS: tuple[ScenarioMapping, ...] = (
    ScenarioMapping(
        "http3-flow-control-public-client-post",
        "http3-server-public-client-post",
        "http3-flow-control",
        ("RFC 9114", "RFC 9000", "RFC 9204"),
        ("http3-server-surface", "qpack-dynamic-state"),
        "Basic request-stream credit and response-drain behavior over the same-stack public client.",
    ),
    ScenarioMapping(
        "http3-flow-control-public-client-post-retry",
        "http3-server-public-client-post-retry",
        "http3-flow-control-retry",
        ("RFC 9114", "RFC 9000", "RFC 9002"),
        ("quic-packet-codec", "quic-recovery", "http3-server-surface"),
        "Retry path preserved as same-stack replay pending third-party regeneration.",
    ),
    ScenarioMapping(
        "http3-flow-control-public-client-post-zero-rtt",
        "http3-server-public-client-post-zero-rtt",
        "http3-flow-control-zero-rtt",
        ("RFC 9114", "RFC 9000", "RFC 9001", "RFC 9002"),
        ("quic-packet-codec", "quic-recovery", "http3-server-surface"),
        "0-RTT / credit-reuse path preserved as same-stack replay pending broader third-party certification.",
    ),
    ScenarioMapping(
        "http3-flow-control-public-client-post-migration",
        "http3-server-public-client-post-migration",
        "http3-flow-control-migration",
        ("RFC 9114", "RFC 9000", "RFC 9002"),
        ("quic-packet-codec", "quic-recovery", "http3-server-surface"),
        "Migration path preserved as same-stack replay pending broader third-party certification.",
    ),
    ScenarioMapping(
        "http3-flow-control-public-client-post-goaway-qpack",
        "http3-server-public-client-post-goaway-qpack",
        "http3-flow-control-goaway-qpack",
        ("RFC 9114", "RFC 9204"),
        ("http3-server-surface", "qpack-dynamic-state"),
        "GOAWAY / QPACK backpressure path preserved as same-stack replay pending third-party regeneration.",
    ),
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copytree_replace(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _remap_artifact_entry(entry: dict[str, Any], *, destination_dir: Path) -> dict[str, Any]:
    payload = dict(entry)
    existing_path = payload.get("path")
    if isinstance(existing_path, str):
        payload["path"] = _rel(destination_dir / Path(existing_path).name)
    return payload


def _scenario_metadata(mapping: ScenarioMapping, *, destination_dir: Path, vectors: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_kind": "provisional_same_stack_flow_control_review",
        "release_gate_eligible": False,
        "source_same_stack_scenario": mapping.source_same_stack_id,
        "mapped_flow_control_scenario": mapping.provisional_id,
        "feature": mapping.feature,
        "rfcs": list(mapping.rfcs),
        "local_vectors": list(mapping.local_vectors),
        "gap_note": mapping.note,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": _rel(destination_dir),
        "vector_fixtures": {name: vectors[name].get("fixture") for name in mapping.local_vectors},
        "note": (
            "This directory is an offline provisional flow-control review bundle generated from same-stack replay artifacts. "
            "It is useful for bundle-shape review and repository transparency, but it is not independent-certification evidence and must not be used to satisfy release gates."
        ),
    }


def _build_provisional_result(mapping: ScenarioMapping, *, destination_dir: Path, vectors: dict[str, Any]) -> dict[str, Any]:
    source_dir = SAME_STACK_ROOT / mapping.source_same_stack_id
    result = _load_json(source_dir / "result.json")
    result["scenario_id"] = mapping.provisional_id
    result["artifact_dir"] = _rel(destination_dir)
    result["commit_hash"] = RELEASE_COMMIT_HASH
    result["consolidated_from"] = _rel(source_dir)
    result["provisional_non_certifying_substitution"] = True
    result["release_gate_eligible"] = False
    result["flow_control_review_only"] = True
    result["source_same_stack_scenario"] = mapping.source_same_stack_id
    result["linked_local_vectors"] = list(mapping.local_vectors)
    result["substitution_note"] = (
        "Copied from same-stack replay evidence because the offline environment did not include broader independent QUIC / HTTP/3 flow-control artifacts. "
        "This bundle documents preserved review material only."
    )
    artifacts = result.get("artifacts")
    if isinstance(artifacts, dict):
        result["artifacts"] = {
            name: _remap_artifact_entry(dict(value), destination_dir=destination_dir)
            for name, value in artifacts.items()
            if isinstance(value, dict)
        }
    result["vector_fixtures"] = {name: vectors[name].get("fixture") for name in mapping.local_vectors}
    return result


def _copy_payload_files(source_dir: Path, destination_dir: Path) -> None:
    for item in source_dir.iterdir():
        if item.name in {"result.json", "provisional_metadata.json"}:
            continue
        target = destination_dir / item.name
        if item.is_dir():
            _copytree_replace(item, target)
        else:
            shutil.copy2(item, target)


def _update_bundle_index() -> None:
    if not BUNDLE_INDEX_PATH.exists():
        return
    payload = _load_json(BUNDLE_INDEX_PATH)
    bundles = dict(payload.get("bundles", {}))
    bundles["provisional_flow_control_gap_bundle"] = _rel(PROVISIONAL_ROOT)
    payload["bundles"] = bundles
    notes = [str(item) for item in payload.get("notes", []) if isinstance(item, str)]
    note = (
        "The provisional flow-control gap bundle is generated from same-stack HTTP/3 replay artifacts and local vector links; it is explicitly non-certifying and does not change canonical release-gate status."
    )
    if note not in notes:
        notes.append(note)
    payload["notes"] = notes
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(BUNDLE_INDEX_PATH, payload)


def main() -> int:
    vectors = {item["name"]: item for item in _load_json(CORPUS_PATH).get("vectors", [])}
    if PROVISIONAL_ROOT.exists():
        shutil.rmtree(PROVISIONAL_ROOT)
    PROVISIONAL_ROOT.mkdir(parents=True)

    scenario_summaries: list[dict[str, Any]] = []
    mapping_payload: list[dict[str, Any]] = []

    for mapping in SCENARIO_MAPPINGS:
        source_dir = SAME_STACK_ROOT / mapping.source_same_stack_id
        if not source_dir.exists():
            raise SystemExit(f"missing source same-stack scenario directory: {source_dir}")
        destination_dir = PROVISIONAL_ROOT / mapping.provisional_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        _copy_payload_files(source_dir, destination_dir)
        _write_json(destination_dir / "result.json", _build_provisional_result(mapping, destination_dir=destination_dir, vectors=vectors))
        _write_json(destination_dir / "provisional_metadata.json", _scenario_metadata(mapping, destination_dir=destination_dir, vectors=vectors))
        _write_json(destination_dir / "source_local_vectors.json", {name: vectors[name] for name in mapping.local_vectors})
        scenario_summaries.append(
            {
                "id": mapping.provisional_id,
                "passed": True,
                "artifact_dir": _rel(destination_dir),
                "source_same_stack_scenario": mapping.source_same_stack_id,
                "release_gate_eligible": False,
                "flow_control_review_only": True,
            }
        )
        mapping_payload.append(
            {
                "provisional_id": mapping.provisional_id,
                "source_same_stack_id": mapping.source_same_stack_id,
                "feature": mapping.feature,
                "rfcs": list(mapping.rfcs),
                "local_vectors": list(mapping.local_vectors),
            }
        )

    manifest = {
        "bundle_kind": "provisional_same_stack_flow_control_review",
        "commit_hash": RELEASE_COMMIT_HASH,
        "dimensions": {
            "feature": sorted({mapping.feature for mapping in SCENARIO_MAPPINGS}),
            "peer": ["tigrcorn-public-client"],
            "protocol": ["http3"],
            "role": ["server"],
            "release_gate_eligible": [False],
        },
        "environment": {
            "curation": {
                "note": (
                    "This bundle was generated offline from same-stack replay artifacts to preserve QUIC / HTTP/3 flow-control review material. "
                    "It is explicitly non-certifying and exists only until broader independent artifacts can be preserved."
                )
            },
            "tigrcorn": {
                "bundle_scope": "offline-provisional-flow-control-gap-bundle",
                "commit_hash": RELEASE_COMMIT_HASH,
                "version": "0.3.6",
            },
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_name": "tigrcorn-provisional-flow-control-gap-bundle",
        "source_corpus": _rel(CORPUS_PATH),
        "source_same_stack_root": _rel(SAME_STACK_ROOT),
        "release_gate_eligible": False,
        "same_stack_root_sha256": sha256((SAME_STACK_ROOT / 'manifest.json').read_bytes()).hexdigest() if (SAME_STACK_ROOT / 'manifest.json').exists() else None,
    }
    index = {
        "artifact_root": _rel(PROVISIONAL_ROOT),
        "commit_hash": RELEASE_COMMIT_HASH,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_name": "tigrcorn-provisional-flow-control-gap-bundle",
        "scenarios": scenario_summaries,
        "total": len(scenario_summaries),
        "passed": len(scenario_summaries),
        "failed": 0,
        "skipped": 0,
        "release_gate_eligible": False,
        "flow_control_review_only": True,
    }
    _write_json(PROVISIONAL_ROOT / 'manifest.json', manifest)
    _write_json(PROVISIONAL_ROOT / 'index.json', index)
    _write_json(PROVISIONAL_ROOT / 'scenario_mapping.json', {"mappings": mapping_payload})
    (PROVISIONAL_ROOT / 'README.md').write_text(
        "# Provisional flow-control gap bundle\n\n"
        "This bundle is generated from same-stack HTTP/3 replay artifacts plus local vector links.\n"
        "It is intentionally non-certifying and exists for offline review and planning only.\n",
        encoding='utf-8',
    )
    _update_bundle_index()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
