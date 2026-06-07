from __future__ import annotations

from .imports import *
from .models import *
from .stats import *

def _resolve_commit_hash(source_root: Path) -> str:
    env_value = os.environ.get('GIT_COMMIT') or os.environ.get('COMMIT_SHA')
    if env_value:
        return env_value
    try:
        completed = subprocess.run(
            ['git', '-C', str(source_root), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=True,
        )
    except Exception:
        return 'unknown'
    value = completed.stdout.strip()
    return value or 'unknown'


def _environment_snapshot(*, matrix: PerfMatrix, command: list[str]) -> dict[str, Any]:
    clock_info = time.get_clock_info('perf_counter')
    platform_id = _default_platform_id()
    return {
        'matrix_name': matrix.matrix_name,
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'cpu_count': os.cpu_count(),
        'perf_counter_resolution': clock_info.resolution,
        'perf_counter_monotonic': clock_info.monotonic,
        'argv': list(command),
        'generated_at_epoch': time.time(),
        'certification_platform': platform_id,
        'matrix_declared_platforms': list(matrix.metadata.get('certification_platforms', [])),
    }
def _default_platform_id() -> str:
    implementation = platform.python_implementation().lower()
    return f"{platform.system().lower()}-{platform.machine().lower()}-{implementation}{sys.version_info.major}.{sys.version_info.minor}"
