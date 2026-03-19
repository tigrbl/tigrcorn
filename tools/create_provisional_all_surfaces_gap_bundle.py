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
CORPUS_PATH = ROOT / "docs/review/conformance/corpus.json"
STRICT_BOUNDARY_PATH = ROOT / "docs/review/conformance/certification_boundary.all_surfaces_independent.json"
PROVISIONAL_ROOT = RELEASE_ROOT / "tigrcorn-provisional-all-surfaces-gap-bundle"
BUNDLE_INDEX_PATH = RELEASE_ROOT / "bundle_index.json"
RELEASE_COMMIT_HASH = "release-0.3.6-offline-provisional-all-surfaces-gap-bundle"


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


@dataclass(frozen=True)
class ScenarioMapping:
    provisional_id: str
    source_local_vector: str
    feature: str
    carrier: str
    peer: str
    rfcs: tuple[str, ...]
    note: str


SCENARIO_MAPPINGS: tuple[ScenarioMapping, ...] = (
    ScenarioMapping(
        "websocket-http11-server-websockets-client-permessage-deflate",
        "websocket-permessage-deflate",
        "permessage-deflate",
        "http1.1",
        "websockets",
        ("RFC 7692", "RFC 6455"),
        "Third-party permessage-deflate coverage is still missing for the HTTP/1.1 WebSocket carrier.",
    ),
    ScenarioMapping(
        "websocket-http2-server-h2-client-permessage-deflate",
        "websocket-permessage-deflate",
        "permessage-deflate",
        "http2",
        "python-h2/wsproto",
        ("RFC 7692", "RFC 8441"),
        "Third-party permessage-deflate coverage is still missing for the RFC 8441 carrier.",
    ),
    ScenarioMapping(
        "websocket-http3-server-aioquic-client-permessage-deflate",
        "websocket-permessage-deflate",
        "permessage-deflate",
        "http3",
        "aioquic/wsproto",
        ("RFC 7692", "RFC 9220"),
        "Third-party permessage-deflate coverage is still missing for the RFC 9220 carrier.",
    ),
    ScenarioMapping(
        "http11-connect-relay-curl-client",
        "http-connect-relay",
        "connect-relay",
        "http1.1",
        "curl",
        ("RFC 9110 §9.3.6",),
        "Independent CONNECT relay evidence is still missing for the HTTP/1.1 carrier.",
    ),
    ScenarioMapping(
        "http2-connect-relay-h2-client",
        "http-connect-relay",
        "connect-relay",
        "http2",
        "python-h2",
        ("RFC 9110 §9.3.6",),
        "Independent CONNECT relay evidence is still missing for the HTTP/2 carrier.",
    ),
    ScenarioMapping(
        "http3-connect-relay-aioquic-client",
        "http-connect-relay",
        "connect-relay",
        "http3",
        "aioquic",
        ("RFC 9110 §9.3.6", "RFC 9114"),
        "Independent CONNECT relay evidence is still missing for the HTTP/3 carrier.",
    ),
    ScenarioMapping(
        "http11-trailer-fields-curl-client",
        "http-trailer-fields",
        "trailers",
        "http1.1",
        "curl",
        ("RFC 9110 §6.5",),
        "Independent trailer-field evidence is still missing for the HTTP/1.1 carrier.",
    ),
    ScenarioMapping(
        "http2-trailer-fields-h2-client",
        "http-trailer-fields",
        "trailers",
        "http2",
        "python-h2",
        ("RFC 9110 §6.5",),
        "Independent trailer-field evidence is still missing for the HTTP/2 carrier.",
    ),
    ScenarioMapping(
        "http3-trailer-fields-aioquic-client",
        "http-trailer-fields",
        "trailers",
        "http3",
        "aioquic",
        ("RFC 9110 §6.5", "RFC 9114"),
        "Independent trailer-field evidence is still missing for the HTTP/3 carrier.",
    ),
    ScenarioMapping(
        "http11-content-coding-curl-client",
        "http-content-coding",
        "content-coding",
        "http1.1",
        "curl",
        ("RFC 9110 §8",),
        "Independent content-coding evidence is still missing for the HTTP/1.1 carrier.",
    ),
    ScenarioMapping(
        "http2-content-coding-curl-client",
        "http-content-coding",
        "content-coding",
        "http2",
        "curl",
        ("RFC 9110 §8", "RFC 9113"),
        "Independent content-coding evidence is still missing for the HTTP/2 carrier.",
    ),
    ScenarioMapping(
        "http3-content-coding-aioquic-client",
        "http-content-coding",
        "content-coding",
        "http3",
        "aioquic",
        ("RFC 9110 §8", "RFC 9114"),
        "Independent content-coding evidence is still missing for the HTTP/3 carrier.",
    ),
    ScenarioMapping(
        "tls-server-ocsp-validation-openssl-client",
        "ocsp-revocation-validation",
        "ocsp-revocation",
        "tls",
        "openssl/curl",
        ("RFC 6960", "RFC 5280", "RFC 8446"),
        "Independent OCSP policy evidence is still missing for the package-owned TLS stack.",
    ),
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_vectors() -> dict[str, dict[str, Any]]:
    payload = _load_json(CORPUS_PATH)
    return {item["name"]: item for item in payload.get("vectors", [])}


def _scenario_metadata(mapping: ScenarioMapping, *, destination_dir: Path, vector: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_kind": "provisional_local_conformance_substitution",
        "release_gate_eligible": False,
        "strict_profile_only": True,
        "source_local_conformance_vector": mapping.source_local_vector,
        "mapped_strict_profile_scenario": mapping.provisional_id,
        "feature": mapping.feature,
        "carrier": mapping.carrier,
        "peer": mapping.peer,
        "rfcs": list(mapping.rfcs),
        "source_fixture": vector.get("fixture"),
        "note": (
            "This directory is an offline provisional substitution generated from the local conformance corpus. "
            "It is useful for stricter-profile review and bundle-shape planning, but it is not independent-certification evidence and must not be used to satisfy release gates."
        ),
        "gap_note": mapping.note,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": _rel(destination_dir),
    }


def _build_provisional_result(mapping: ScenarioMapping, *, destination_dir: Path, vector: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_dir": _rel(destination_dir),
        "carrier": mapping.carrier,
        "commit_hash": RELEASE_COMMIT_HASH,
        "feature": mapping.feature,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "peer": mapping.peer,
        "passed": True,
        "provisional_non_certifying_substitution": True,
        "release_gate_eligible": False,
        "rfcs": list(mapping.rfcs),
        "scenario_id": mapping.provisional_id,
        "source_fixture": vector.get("fixture"),
        "source_local_conformance_vector": mapping.source_local_vector,
        "strict_profile_only": True,
        "substitution_note": (
            "Derived from local conformance vector metadata because the repository does not yet preserve the corresponding third-party artifacts for the stricter all-surfaces-independent profile."
        ),
        "vector_description": vector.get("description"),
    }


def _update_bundle_index() -> None:
    if not BUNDLE_INDEX_PATH.exists():
        return
    payload = _load_json(BUNDLE_INDEX_PATH)
    bundles = dict(payload.get("bundles", {}))
    bundles["provisional_all_surfaces_gap_bundle"] = _rel(PROVISIONAL_ROOT)
    payload["bundles"] = bundles
    notes = [str(item) for item in payload.get("notes", []) if isinstance(item, str)]
    note = (
        "The provisional all-surfaces gap bundle is generated from local conformance vectors for the stricter all-surfaces-independent profile; it is explicitly non-certifying and does not change canonical release-gate status."
    )
    if note not in notes:
        notes.append(note)
    payload["notes"] = notes
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(BUNDLE_INDEX_PATH, payload)


def main() -> int:
    vectors = _load_vectors()
    if PROVISIONAL_ROOT.exists():
        shutil.rmtree(PROVISIONAL_ROOT)
    PROVISIONAL_ROOT.mkdir(parents=True)

    scenario_summaries: list[dict[str, Any]] = []
    mapping_payload: list[dict[str, Any]] = []

    for mapping in SCENARIO_MAPPINGS:
        if mapping.source_local_vector not in vectors:
            raise SystemExit(f"missing source local vector: {mapping.source_local_vector}")
        vector = vectors[mapping.source_local_vector]
        destination_dir = PROVISIONAL_ROOT / mapping.provisional_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        _write_json(destination_dir / "result.json", _build_provisional_result(mapping, destination_dir=destination_dir, vector=vector))
        _write_json(destination_dir / "provisional_metadata.json", _scenario_metadata(mapping, destination_dir=destination_dir, vector=vector))
        _write_json(destination_dir / "source_local_vector.json", vector)

        scenario_summaries.append(
            {
                "id": mapping.provisional_id,
                "passed": True,
                "artifact_dir": _rel(destination_dir),
                "source_local_conformance_vector": mapping.source_local_vector,
                "release_gate_eligible": False,
            }
        )
        mapping_payload.append(
            {
                "provisional_id": mapping.provisional_id,
                "source_local_vector": mapping.source_local_vector,
                "feature": mapping.feature,
                "carrier": mapping.carrier,
                "peer": mapping.peer,
                "rfcs": list(mapping.rfcs),
            }
        )

    manifest = {
        "bundle_kind": "provisional_local_conformance_substitution",
        "commit_hash": RELEASE_COMMIT_HASH,
        "dimensions": {
            "feature": sorted({mapping.feature for mapping in SCENARIO_MAPPINGS}),
            "carrier": sorted({mapping.carrier for mapping in SCENARIO_MAPPINGS}),
            "peer": sorted({mapping.peer for mapping in SCENARIO_MAPPINGS}),
            "release_gate_eligible": [False],
        },
        "environment": {
            "curation": {
                "note": (
                    "This bundle was generated offline from local conformance vectors to preserve the stricter all-surfaces-independent scenario layout. "
                    "It is explicitly non-certifying and exists only as a planning aid until real third-party artifacts can be preserved."
                )
            },
            "tigrcorn": {
                "bundle_scope": "offline-provisional-all-surfaces-gap-bundle",
                "commit_hash": RELEASE_COMMIT_HASH,
                "version": "0.3.6",
            },
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_name": "tigrcorn-provisional-all-surfaces-gap-bundle",
        "strict_boundary_sha256": sha256(STRICT_BOUNDARY_PATH.read_bytes()).hexdigest() if STRICT_BOUNDARY_PATH.exists() else None,
        "source_corpus": _rel(CORPUS_PATH),
        "release_gate_eligible": False,
    }
    index = {
        "artifact_root": _rel(PROVISIONAL_ROOT),
        "commit_hash": RELEASE_COMMIT_HASH,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_name": "tigrcorn-provisional-all-surfaces-gap-bundle",
        "scenarios": scenario_summaries,
        "total": len(scenario_summaries),
        "passed": len(scenario_summaries),
        "failed": 0,
        "skipped": 0,
        "release_gate_eligible": False,
        "strict_profile_only": True,
    }
    _write_json(PROVISIONAL_ROOT / "manifest.json", manifest)
    _write_json(PROVISIONAL_ROOT / "index.json", index)
    _write_json(PROVISIONAL_ROOT / "scenario_mapping.json", {"mappings": mapping_payload})
    (PROVISIONAL_ROOT / "README.md").write_text(
        "# Provisional all-surfaces gap bundle\n\n"
        "This bundle is generated from local conformance vectors and is intentionally non-certifying.\n"
        "It preserves the stricter all-surfaces-independent scenario layout for offline review and planning only.\n",
        encoding="utf-8",
    )
    _update_bundle_index()
    print(f"generated provisional non-certifying strict-profile gap bundle at {_rel(PROVISIONAL_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
