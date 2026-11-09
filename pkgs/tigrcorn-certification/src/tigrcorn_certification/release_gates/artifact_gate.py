from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *

def evaluate_certification_artifact_release_gate(
    source_root: str | Path,
    *,
    boundary: Mapping[str, Any] | None = None,
    artifact_root: str | Path | None = None,
    signature_key: str | bytes | None = None,
    checked_files: list[str] | None = None,
    artifact_status: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    from tigrcorn_certification.artifacts import verify_output_tree

    source_root = Path(source_root)
    boundary = dict(boundary or {})
    artifact_config = boundary.get('certification_artifacts', {})
    if not isinstance(artifact_config, Mapping):
        artifact_config = {}
    root_value = artifact_root or artifact_config.get('artifact_root') or DEFAULT_CERTIFICATION_ARTIFACT_ROOT
    root = source_root / Path(root_value)
    key_value = signature_key if signature_key is not None else artifact_config.get('manifest_signature_key')
    result = verify_output_tree(root, key=key_value, require_signature=True)
    if checked_files is not None:
        checked_files.extend(str(path) for path in result.get('checked_files', []))
    failures = [f'certification artifacts: {item}' for item in result.get('failures', [])]
    if artifact_status is not None:
        artifact_status['certification_artifacts'] = {
            'artifact_root': str(root),
            'failed': bool(failures),
            'files': list(result.get('files', [])),
            'release_eligible': bool(result.get('release_eligible', False)),
        }
    return failures

__all__ = [name for name in globals() if not name.startswith('__')]

