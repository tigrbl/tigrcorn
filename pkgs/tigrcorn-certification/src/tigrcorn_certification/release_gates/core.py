from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *
from .independent import *
from .contract_registry import *
from .artifact_gate import *
from .supply_chain_gate import *
from .docs import *

def evaluate_release_gates(
    source_root: str | Path,
    *,
    boundary_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
    independent_matrix_path: str | Path | None = None,
    same_stack_matrix_path: str | Path | None = None,
) -> ReleaseGateReport:
    source_root = Path(source_root)
    boundary_file = source_root / (Path(boundary_path) if boundary_path is not None else DEFAULT_BOUNDARY_PATH)
    corpus_file = source_root / (Path(corpus_path) if corpus_path is not None else DEFAULT_CORPUS_PATH)
    independent_file = source_root / (Path(independent_matrix_path) if independent_matrix_path is not None else DEFAULT_INDEPENDENT_MATRIX_PATH)
    same_stack_file = source_root / (Path(same_stack_matrix_path) if same_stack_matrix_path is not None else DEFAULT_SAME_STACK_MATRIX_PATH)

    failures: list[str] = []
    checked_files: list[str] = [str(boundary_file), str(corpus_file), str(independent_file), str(same_stack_file)]
    rfc_status: dict[str, dict[str, Any]] = {}
    artifact_status: dict[str, dict[str, Any]] = {}

    if not boundary_file.exists():
        failures.append(f'missing certification boundary file: {boundary_file}')
        return ReleaseGateReport(False, failures, checked_files, rfc_status, artifact_status)

    boundary = load_certification_boundary(boundary_file)
    canonical_doc = str(boundary.get('canonical_doc', 'docs/review/conformance/CERTIFICATION_BOUNDARY.md'))
    gates = dict(boundary.get('gates', {}))
    docs_to_check = [source_root / Path(item) for item in boundary.get('docs_that_must_reference_boundary', [])]
    checked_files.extend(str(path) for path in docs_to_check)

    if gates.get('require_docs_reference_canonical_boundary', False):
        failures.extend(_validate_boundary_references(canonical_doc=canonical_doc, docs_to_check=docs_to_check))

    corpus_payload: dict[str, Any] | None
    if gates.get('require_conformance_corpus', False):
        if not corpus_file.exists():
            failures.append(f'missing conformance corpus: {corpus_file}')
            corpus_payload = None
        else:
            corpus_payload = load_conformance_corpus(corpus_file)
    else:
        corpus_payload = load_conformance_corpus(corpus_file) if corpus_file.exists() else None

    independent_matrix = None
    if gates.get('require_independent_matrix', False):
        if not independent_file.exists():
            failures.append(f'missing independent certification matrix: {independent_file}')
        else:
            independent_matrix = load_external_matrix(independent_file)
            failures.extend(_fail_closed_for_matrix_metadata(independent_matrix, matrix_name='independent certification matrix'))
            if not independent_matrix.scenarios:
                failures.append('independent certification matrix does not include any declared scenarios')
    elif independent_file.exists():
        independent_matrix = load_external_matrix(independent_file)

    same_stack_matrix = None
    if same_stack_file.exists():
        same_stack_matrix = load_external_matrix(same_stack_file)
        failures.extend(_fail_closed_for_matrix_metadata(same_stack_matrix, matrix_name='same-stack replay matrix'))
        if any(scenario.evidence_tier != 'same_stack_replay' for scenario in same_stack_matrix.scenarios):
            failures.append('same-stack replay matrix contains a scenario outside the same_stack_replay tier')
    elif gates.get('require_docs_reference_canonical_boundary', False):
        failures.append(f'missing same-stack replay matrix: {same_stack_file}')

    if independent_matrix is not None:
        failures.extend(_evaluate_independent_matrix(independent_matrix.scenarios, gates=gates))

    if gates.get('require_package_owned_tls13_subsystem', False):
        tls_wrapper_path = source_root / DEFAULT_TLS_WRAPPER_PATH
        checked_files.append(str(tls_wrapper_path))
        if not tls_wrapper_path.exists():
            failures.append(f'missing TLS wrapper module: {tls_wrapper_path}')
        else:
            tls_wrapper_text = tls_wrapper_path.read_text(encoding='utf-8')
            if 'ssl.create_default_context' in tls_wrapper_text:
                failures.append(
                    'package-owned TLS 1.3 release gate failed because src/tigrcorn/security/tls.py still delegates TCP/TLS to ssl.create_default_context'
                )

    if gates.get('require_rfc_evidence_map', False) and corpus_payload is not None and independent_matrix is not None and same_stack_matrix is not None:
        failures.extend(
            _evaluate_rfc_evidence(
                source_root=source_root,
                boundary=boundary,
                corpus_payload=corpus_payload,
                independent_matrix_scenarios=independent_matrix.scenarios,
                same_stack_matrix_scenarios=same_stack_matrix.scenarios,
                checked_files=checked_files,
                rfc_status=rfc_status,
                artifact_status=artifact_status,
            )
        )

    if gates.get('require_governance_graph', False):
        failures.extend(_evaluate_governance_graph(source_root=source_root, checked_files=checked_files))

    if gates.get('require_contract_registry_traceability', False):
        failures.extend(
            evaluate_contract_registry_release_gate(
                source_root,
                boundary=boundary,
                require_ssot_links=bool(gates.get('require_contract_registry_ssot_links', False)),
                checked_files=checked_files,
                artifact_status=artifact_status,
            )
        )

    if gates.get('require_signed_certification_artifacts', False):
        failures.extend(
            evaluate_certification_artifact_release_gate(
                source_root,
                boundary=boundary,
                checked_files=checked_files,
                artifact_status=artifact_status,
            )
        )

    if gates.get('require_supply_chain_release_provenance', False):
        failures.extend(
            evaluate_supply_chain_release_gate(
                source_root,
                boundary=boundary,
                checked_files=checked_files,
                artifact_status=artifact_status,
            )
        )

    return ReleaseGateReport(not failures, failures, checked_files, rfc_status, artifact_status)


def assert_release_ready(
    source_root: str | Path,
    *,
    boundary_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
    independent_matrix_path: str | Path | None = None,
    same_stack_matrix_path: str | Path | None = None,
) -> None:
    report = evaluate_release_gates(
        source_root,
        boundary_path=boundary_path,
        corpus_path=corpus_path,
        independent_matrix_path=independent_matrix_path,
        same_stack_matrix_path=same_stack_matrix_path,
    )
    if not report.passed:
        details = '\n'.join(f'- {item}' for item in report.failures)
        raise ReleaseGateError(f'release gates failed:\n{details}')

__all__ = [name for name in globals() if not name.startswith('__')]

