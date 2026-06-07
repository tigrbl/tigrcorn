from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

DEFAULT_PERFORMANCE_MATRIX_PATH = Path('docs/review/performance/performance_matrix.json')
DEFAULT_BASELINE_ARTIFACT_ROOT = Path('docs/review/performance/artifacts/phase6_reference_baseline')
DEFAULT_CURRENT_ARTIFACT_ROOT = Path('docs/review/performance/artifacts/phase6_current_release')
