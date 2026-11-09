"""Execute a single benchmark profile in a fresh interpreter."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .artifacts import _jsonable
from .models import PerfProfile


def main() -> None:
    from benchmarks.common import _rss_kib
    from benchmarks.registry import get_driver

    output = Path(sys.argv[1])
    profile = PerfProfile(**json.load(sys.stdin))
    driver = get_driver(profile.driver)
    peak_before = _rss_kib()
    measurement = driver(profile, source_root=Path.cwd())
    measurement['metadata'] = {
        **measurement.get('metadata', {}),
        'worker_pid': os.getpid(),
        'worker_peak_before_workload_kib': peak_before,
    }
    output.write_text(json.dumps(_jsonable(measurement)), encoding='utf-8')


if __name__ == '__main__':
    main()
