from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..interop_runner import run_external_matrix
from ..release_gates import evaluate_promotion_target, evaluate_release_gates

DEFAULT_PRELIGHT_SCENARIOS: tuple[str, ...] = (
    'http3-server-aioquic-client-post',
    'websocket-http3-server-aioquic-client',
)
DEFAULT_BUNDLE_NAME = 'tigrcorn-aioquic-adapter-preflight-bundle'
DEFAULT_STATUS_DOC = 'docs/review/conformance/AIOQUIC_ADAPTER_PREFLIGHT.md'
DEFAULT_STATUS_JSON = 'docs/review/conformance/aioquic_adapter_preflight.current.json'
DEFAULT_DELIVERY_NOTES = 'docs/review/conformance/delivery/DELIVERY_NOTES_AIOQUIC_ADAPTER_PREFLIGHT.md'
DEFAULT_MATRIX_PATH = 'docs/review/conformance/external_matrix.release.json'
DEFAULT_RELEASE_ROOT = 'docs/review/conformance/releases/0.3.9/release-0.3.9'
