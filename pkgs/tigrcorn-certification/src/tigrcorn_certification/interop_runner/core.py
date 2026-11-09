from __future__ import annotations

from .imports import *
from .matrix import load_external_matrix
from .models import *
from .runner import ExternalInteropRunner

def run_external_matrix(
    matrix_path: str | Path,
    *,
    artifact_root: str | Path,
    source_root: str | Path | None = None,
    scenario_ids: Iterable[str] | None = None,
    strict: bool = False,
) -> InteropRunSummary:
    matrix = load_external_matrix(matrix_path)
    runner = ExternalInteropRunner(matrix=matrix, artifact_root=artifact_root, source_root=source_root)
    return runner.run(scenario_ids=scenario_ids, strict=strict)


# ----- Internal helpers --------------------------------------------------

__all__ = [name for name in globals() if not name.startswith('__')]
