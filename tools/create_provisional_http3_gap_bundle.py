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
PROVISIONAL_ROOT = RELEASE_ROOT / "tigrcorn-provisional-http3-gap-bundle"
BUNDLE_INDEX_PATH = RELEASE_ROOT / "bundle_index.json"
MATRIX_PATH = ROOT / "docs/review/conformance/external_matrix.release.json"
RELEASE_COMMIT_HASH = "release-0.3.6-offline-provisional-gap-bundle"


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


@dataclass(frozen=True)
class ScenarioMapping:
    provisional_id: str
    source_same_stack_id: str
    feature: str
    rfcs: tuple[str, ...]


SCENARIO_MAPPINGS: tuple[ScenarioMapping, ...] = (
    ScenarioMapping("http3-server-aioquic-client-post", "http3-server-public-client-post", "post-echo", ("RFC 9114", "RFC 9204")),
    ScenarioMapping("http3-server-aioquic-client-post-mtls", "http3-server-public-client-post-mtls", "post-echo-mtls", ("RFC 9114", "RFC 9001", "RFC 5280")),
    ScenarioMapping("http3-server-aioquic-client-post-retry", "http3-server-public-client-post-retry", "post-echo-retry", ("RFC 9114", "RFC 9000", "RFC 9002")),
    ScenarioMapping("http3-server-aioquic-client-post-resumption", "http3-server-public-client-post-resumption", "post-echo-resumption", ("RFC 9114", "RFC 9000", "RFC 9001", "RFC 9002")),
    ScenarioMapping("http3-server-aioquic-client-post-zero-rtt", "http3-server-public-client-post-zero-rtt", "post-echo-zero-rtt", ("RFC 9114", "RFC 9000", "RFC 9001", "RFC 9002")),
    ScenarioMapping("http3-server-aioquic-client-post-migration", "http3-server-public-client-post-migration", "post-echo-migration", ("RFC 9114", "RFC 9000", "RFC 9002")),
    ScenarioMapping("http3-server-aioquic-client-post-goaway-qpack", "http3-server-public-client-post-goaway-qpack", "post-echo-goaway-qpack", ("RFC 9114", "RFC 9204")),
    ScenarioMapping("websocket-http3-server-aioquic-client", "websocket-http3-server-public-client", "websocket-rfc9220-echo", ("RFC 9220", "RFC 9114")),
    ScenarioMapping("websocket-http3-server-aioquic-client-mtls", "websocket-http3-server-public-client-mtls", "websocket-rfc9220-echo-mtls", ("RFC 9220", "RFC 9114", "RFC 9001", "RFC 5280")),
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


def _scenario_metadata(mapping: ScenarioMapping, *, destination_dir: Path) -> dict[str, Any]:
    return {
        "bundle_kind": "provisional_same_stack_substitution",
        "release_gate_eligible": False,
        "source_same_stack_scenario": mapping.source_same_stack_id,
        "mapped_independent_scenario": mapping.provisional_id,
        "feature": mapping.feature,
        "rfcs": list(mapping.rfcs),
        "note": (
            "This directory is an offline provisional substitution generated from same-stack replay artifacts. "
            "It is useful for bundle-shape review and documentation, but it is not independent-certification evidence and must not be used to satisfy release gates."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_dir": _rel(destination_dir),
    }


def _build_provisional_result(mapping: ScenarioMapping, *, destination_dir: Path) -> dict[str, Any]:
    source_dir = SAME_STACK_ROOT / mapping.source_same_stack_id
    result = _load_json(source_dir / "result.json")
    result["scenario_id"] = mapping.provisional_id
    result["artifact_dir"] = _rel(destination_dir)
    result["commit_hash"] = RELEASE_COMMIT_HASH
    result["consolidated_from"] = _rel(source_dir)
    result["provisional_non_certifying_substitution"] = True
    result["release_gate_eligible"] = False
    result["source_same_stack_scenario"] = mapping.source_same_stack_id
    result["substitution_note"] = (
        "Copied from same-stack replay evidence because the offline environment did not include aioquic. "
        "The preserved artifacts remain non-certifying stand-ins until the true third-party bundle is regenerated."
    )
    artifacts = result.get("artifacts")
    if isinstance(artifacts, dict):
        result["artifacts"] = {
            name: _remap_artifact_entry(dict(value), destination_dir=destination_dir)
            for name, value in artifacts.items()
            if isinstance(value, dict)
        }
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
    bundles["provisional_http3_gap_bundle"] = _rel(PROVISIONAL_ROOT)
    payload["bundles"] = bundles
    notes = [str(item) for item in payload.get("notes", []) if isinstance(item, str)]
    provisional_note = (
        "The provisional HTTP/3 gap bundle is a same-stack substitution aid generated offline; it is explicitly non-certifying and does not change release-gate status."
    )
    if provisional_note not in notes:
        notes.append(provisional_note)
    payload["notes"] = notes
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(BUNDLE_INDEX_PATH, payload)


def main() -> int:
    if not SAME_STACK_ROOT.exists():
        raise SystemExit(f"missing same-stack replay root: {SAME_STACK_ROOT}")

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
        _write_json(destination_dir / "result.json", _build_provisional_result(mapping, destination_dir=destination_dir))
        _write_json(destination_dir / "provisional_metadata.json", _scenario_metadata(mapping, destination_dir=destination_dir))

        scenario_summaries.append(
            {
                "id": mapping.provisional_id,
                "passed": True,
                "artifact_dir": _rel(destination_dir),
                "source_same_stack_scenario": mapping.source_same_stack_id,
                "release_gate_eligible": False,
            }
        )
        mapping_payload.append(
            {
                "provisional_id": mapping.provisional_id,
                "source_same_stack_id": mapping.source_same_stack_id,
                "feature": mapping.feature,
                "rfcs": list(mapping.rfcs),
            }
        )

    manifest = {
        "bundle_kind": "provisional_same_stack_substitution",
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
                    "This bundle was generated offline from same-stack replay artifacts to preserve the missing independent-scenario directory layout. "
                    "It is explicitly non-certifying and exists only as a remediation aid until aioquic-backed preserved artifacts can be regenerated."
                )
            },
            "tigrcorn": {
                "bundle_scope": "offline-provisional-gap-bundle",
                "commit_hash": RELEASE_COMMIT_HASH,
                "version": "0.3.6",
            },
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_name": "tigrcorn-provisional-http3-gap-bundle",
        "matrix_sha256": sha256(MATRIX_PATH.read_bytes()).hexdigest(),
        "source_bundles": [_rel(SAME_STACK_ROOT)],
        "release_gate_eligible": False,
    }
    index = {
        "artifact_root": _rel(PROVISIONAL_ROOT),
        "commit_hash": RELEASE_COMMIT_HASH,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_name": "tigrcorn-provisional-http3-gap-bundle",
        "scenarios": scenario_summaries,
        "total": len(scenario_summaries),
        "passed": len(scenario_summaries),
        "failed": 0,
        "skipped": 0,
        "release_gate_eligible": False,
    }
    _write_json(PROVISIONAL_ROOT / "manifest.json", manifest)
    _write_json(PROVISIONAL_ROOT / "index.json", index)
    _write_json(PROVISIONAL_ROOT / "scenario_mapping.json", {"mappings": mapping_payload})
    (PROVISIONAL_ROOT / "README.md").write_text(
        "# Provisional HTTP/3 gap bundle\n\n"
        "This bundle is generated from same-stack replay artifacts and is intentionally non-certifying.\n"
        "It preserves the missing third-party scenario directory layout for offline review and gap analysis only.\n",
        encoding="utf-8",
    )
    _update_bundle_index()
    print(f"generated provisional non-certifying gap bundle at {_rel(PROVISIONAL_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
