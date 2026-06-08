from __future__ import annotations

from .imports import *
from .models import *
from .scenario import ExternalInteropScenarioMixin
from .environment import *
from .matrix import *
from .helpers import *

class ExternalInteropRunner(ExternalInteropScenarioMixin):
    def __init__(self, *, matrix: InteropMatrix, artifact_root: str | Path, source_root: str | Path | None = None) -> None:
        for scenario in matrix.scenarios:
            _validate_scenario_provenance(scenario)
        self.matrix = matrix
        self.artifact_root = Path(artifact_root)
        self.source_root = Path(source_root) if source_root is not None else Path.cwd()
        self.commit_hash = detect_source_revision(self.source_root)
        self.environment_manifest = build_environment_manifest(self.source_root, commit_hash=self.commit_hash)

    def run(self, *, scenario_ids: Iterable[str] | None = None, strict: bool = False) -> InteropRunSummary:
        selected = set(scenario_ids or ())
        scenarios = self.matrix.enabled_scenarios
        if selected:
            scenarios = [scenario for scenario in scenarios if scenario.id in selected]
        run_root = self.artifact_root / self.commit_hash / self.matrix.name
        run_root.mkdir(parents=True, exist_ok=True)
        bundle_kind = str(self.matrix.metadata.get('bundle_kind', self.matrix.metadata.get('evidence_tier', 'mixed')) or 'mixed')
        wrapper_families = dict(self.matrix.metadata.get('independent_harness_wrapper_families', {}))
        _write_json(
            run_root / 'manifest.json',
            {
                'matrix_name': self.matrix.name,
                'bundle_kind': bundle_kind,
                'artifact_schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'required_bundle_files': list(INTEROP_BUNDLE_REQUIRED_FILES),
                'required_scenario_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
                'commit_hash': self.commit_hash,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'dimensions': summarize_matrix_dimensions(self.matrix),
                'environment': self.environment_manifest,
                'matrix_sha256': _sha256_bytes(json.dumps(_matrix_to_json(self.matrix), sort_keys=True).encode('utf-8')),
                'wrapper_families': wrapper_families,
            },
        )
        results: list[InteropScenarioResult] = []
        passed = 0
        failed = 0
        skipped = len([scenario for scenario in self.matrix.scenarios if scenario not in scenarios])
        for scenario in scenarios:
            result = self._run_scenario(scenario, run_root)
            results.append(result)
            if result.passed:
                passed += 1
            else:
                failed += 1
                if strict:
                    break
        summary = InteropRunSummary(
            matrix_name=self.matrix.name,
            commit_hash=self.commit_hash,
            artifact_root=str(run_root),
            total=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            scenarios=results,
        )
        root_index_payload = {
            'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
            'bundle_kind': bundle_kind,
            'required_bundle_files': list(INTEROP_BUNDLE_REQUIRED_FILES),
            'required_scenario_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
            'matrix_name': summary.matrix_name,
            'commit_hash': summary.commit_hash,
            'artifact_root': summary.artifact_root,
            'total': summary.total,
            'passed': summary.passed,
            'failed': summary.failed,
            'skipped': summary.skipped,
            'wrapper_families': wrapper_families,
            'scenarios': [
                {
                    'id': item.scenario_id,
                    'passed': item.passed,
                    'artifact_dir': item.artifact_dir,
                    'assertions_failed': item.assertions_failed,
                    'error': item.error,
                    'summary_path': str(Path(item.artifact_dir) / 'summary.json'),
                    'index_path': str(Path(item.artifact_dir) / 'index.json'),
                    'result_path': str(Path(item.artifact_dir) / 'result.json'),
                }
                for item in summary.scenarios
            ],
        }
        _write_json(run_root / 'index.json', root_index_payload)
        _write_json(
            run_root / 'summary.json',
            {
                'schema_version': INTEROP_ARTIFACT_SCHEMA_VERSION,
                'bundle_kind': bundle_kind,
                'matrix_name': summary.matrix_name,
                'commit_hash': summary.commit_hash,
                'artifact_root': summary.artifact_root,
                'total': summary.total,
                'passed': summary.passed,
                'failed': summary.failed,
                'skipped': summary.skipped,
                'scenario_ids': [item.scenario_id for item in summary.scenarios],
                'required_bundle_files': list(INTEROP_BUNDLE_REQUIRED_FILES),
                'required_scenario_files': list(INTEROP_SCENARIO_REQUIRED_FILES),
                'wrapper_families': wrapper_families,
            },
        )
        return summary

__all__ = [name for name in globals() if not name.startswith('__')]
