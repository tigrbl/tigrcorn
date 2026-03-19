from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.interop_runner import ExternalInteropRunner, load_external_matrix, summarize_matrix_dimensions
from tigrcorn.version import __version__

MATRIX_PATH = ROOT / "docs/review/conformance/external_matrix.release.json"
CANONICAL_RELEASE_ROOT = ROOT / "docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-independent-certification-release-matrix"
BUNDLE_INDEX_PATH = ROOT / "docs/review/conformance/releases/0.3.6/release-0.3.6/bundle_index.json"
RELEASE_COMMIT_HASH = "release-0.3.6"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="regenerate-independent-http3-release-bundle",
        description="Regenerate the pending third-party HTTP/3 / RFC 9220 certification scenarios and optionally promote them into the canonical 0.3.6 independent release bundle.",
    )
    parser.add_argument(
        "--artifact-root",
        default=str(ROOT / ".artifacts" / "independent-http3-regeneration"),
        help="Directory where the fresh interop run should be written before optional promotion.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario identifier to run. Repeat to constrain the regeneration set. Defaults to all pending aioquic scenarios declared in the release matrix.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Copy freshly regenerated scenario artifacts into the canonical 0.3.6 independent release bundle and update its index / manifest.",
    )
    parser.add_argument(
        "--enable-matrix",
        action="store_true",
        help="Mark regenerated scenarios as enabled inside docs/review/conformance/external_matrix.release.json after a successful promoted run.",
    )
    return parser


def _assert_optional_runtime() -> None:
    missing = [name for name in ("aioquic", "wsproto") if importlib.util.find_spec(name) is None]
    if missing:
        names = ", ".join(sorted(missing))
        raise SystemExit(
            f"missing optional certification runtime dependencies: {names}. Install the certification extra before regenerating the true third-party HTTP/3 bundle. If you are working offline and need a non-certifying stand-in bundle for review only, run `python tools/create_provisional_http3_gap_bundle.py`."
        )


def _pending_scenarios() -> tuple[Any, list[str]]:
    matrix = load_external_matrix(MATRIX_PATH)
    pending_ids = [str(item) for item in matrix.metadata.get("pending_third_party_http3_scenarios", [])]
    if not pending_ids:
        pending_ids = [scenario.id for scenario in matrix.scenarios if scenario.peer == "aioquic"]
    return matrix, pending_ids


def _enable_selected_scenarios(matrix: Any, scenario_ids: set[str]) -> None:
    for scenario in matrix.scenarios:
        enabled = scenario.id in scenario_ids
        scenario.enabled = enabled
        scenario.peer_process.enabled = enabled


def _copytree_replace(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _update_index(canonical_root: Path, summary: Any, *, source_bundle: str) -> None:
    index_path = canonical_root / "index.json"
    if index_path.exists():
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        payload = {"scenarios": []}
    scenarios = {item["id"]: dict(item) for item in payload.get("scenarios", []) if isinstance(item, dict) and item.get("id")}
    for result in summary.scenarios:
        scenarios[result.scenario_id] = {
            "id": result.scenario_id,
            "passed": bool(result.passed),
            "artifact_dir": str(canonical_root / result.scenario_id),
            "assertions_failed": list(result.assertions_failed),
            "error": result.error,
            "source_bundle": source_bundle,
        }
    ordered = [scenarios[key] for key in sorted(scenarios)]
    payload.update(
        {
            "artifact_root": str(canonical_root),
            "commit_hash": RELEASE_COMMIT_HASH,
            "matrix_name": "tigrcorn-independent-certification-release-matrix",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": ordered,
            "total": len(ordered),
            "passed": sum(1 for item in ordered if item.get("passed")),
            "failed": sum(1 for item in ordered if not item.get("passed")),
            "skipped": 0,
        }
    )
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _update_manifest(canonical_root: Path, matrix: Any, *, source_bundle: str) -> None:
    manifest_path = canonical_root / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    source_bundles = [str(item) for item in existing.get("source_bundles", []) if isinstance(item, str)]
    if source_bundle not in source_bundles:
        source_bundles.append(source_bundle)
    manifest = {
        "bundle_kind": "independent_certification",
        "commit_hash": RELEASE_COMMIT_HASH,
        "dimensions": summarize_matrix_dimensions(matrix),
        "environment": {
            "curation": {
                "note": "This canonical 0.3.6 release root now includes freshly regenerated third-party HTTP/3 / RFC 9220 artifacts in addition to the previously curated preserved evidence."
            },
            "tigrcorn": {
                "bundle_scope": "curated-preserved-artifacts",
                "commit_hash": RELEASE_COMMIT_HASH,
                "version": __version__,
            },
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_name": matrix.name,
        "matrix_sha256": sha256(MATRIX_PATH.read_bytes()).hexdigest(),
        "source_bundles": source_bundles,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _update_bundle_index() -> None:
    if not BUNDLE_INDEX_PATH.exists():
        return
    payload = json.loads(BUNDLE_INDEX_PATH.read_text(encoding="utf-8"))
    notes = [str(item) for item in payload.get("notes", []) if isinstance(item, str)]
    replacement = "The independent certification matrix includes preserved passing artifacts for all declared third-party HTTP/3 / RFC 9220 scenarios once this bundle has been regenerated and promoted."
    notes = [replacement if "disabled third-party HTTP/3 / RFC 9220" in item else item for item in notes]
    if replacement not in notes:
        notes.append(replacement)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["notes"] = notes
    BUNDLE_INDEX_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _enable_matrix_entries(scenario_ids: set[str]) -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    changed = False
    for scenario in payload.get("scenarios", payload.get("matrix", {}).get("scenarios", [])):
        if not isinstance(scenario, dict) or scenario.get("id") not in scenario_ids:
            continue
        scenario["enabled"] = True
        peer_process = scenario.get("peer_process")
        if isinstance(peer_process, dict):
            peer_process["enabled"] = True
        metadata = scenario.get("metadata")
        if isinstance(metadata, dict):
            metadata["certification_status"] = "ready_for_preserved_artifact_promotion"
            metadata.pop("blocking_reason", None)
        changed = True
    if changed:
        MATRIX_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _assert_optional_runtime()
    matrix, pending_ids = _pending_scenarios()
    selected_ids = set(args.scenario or pending_ids)
    if not selected_ids:
        raise SystemExit("no pending aioquic scenarios were found in the release matrix")
    _enable_selected_scenarios(matrix, selected_ids)

    artifact_root = Path(args.artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    prior_commit = os.environ.get("TIGRCORN_COMMIT_HASH")
    os.environ["TIGRCORN_COMMIT_HASH"] = RELEASE_COMMIT_HASH
    try:
        runner = ExternalInteropRunner(matrix=matrix, artifact_root=artifact_root, source_root=ROOT)
        summary = runner.run(strict=True)
    finally:
        if prior_commit is None:
            os.environ.pop("TIGRCORN_COMMIT_HASH", None)
        else:
            os.environ["TIGRCORN_COMMIT_HASH"] = prior_commit

    if summary.failed:
        failures = [item.scenario_id for item in summary.scenarios if not item.passed]
        names = ", ".join(sorted(failures))
        print(f"fresh interop run completed with failures: {names}", file=sys.stderr)
        return 1

    source_bundle = str(Path(summary.artifact_root))
    print(f"fresh third-party HTTP/3 artifacts written to {source_bundle}")

    if args.promote:
        for result in summary.scenarios:
            _copytree_replace(Path(result.artifact_dir), CANONICAL_RELEASE_ROOT / result.scenario_id)
        _update_index(CANONICAL_RELEASE_ROOT, summary, source_bundle=source_bundle)
        _update_manifest(CANONICAL_RELEASE_ROOT, matrix, source_bundle=source_bundle)
        _update_bundle_index()
        print(f"promoted {len(summary.scenarios)} scenarios into {CANONICAL_RELEASE_ROOT}")
        if args.enable_matrix:
            _enable_matrix_entries(selected_ids)
            print(f"enabled {len(selected_ids)} scenarios in {MATRIX_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
