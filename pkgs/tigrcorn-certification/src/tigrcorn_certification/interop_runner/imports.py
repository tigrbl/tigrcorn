from __future__ import annotations

import json
import os
import platform
import re
import selectors
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from tigrcorn_config.observability_surface import QLOG_EXPERIMENTAL_SCHEMA_VERSION
from tigrcorn_transports.quic.packets import (
    QuicLongHeaderPacket,
    QuicRetryPacket,
    QuicShortHeaderPacket,
    QuicVersionNegotiationPacket,
    decode_packet,
    split_coalesced_packets,
)
from tigrcorn_core.version import __version__

DEFAULT_READY_TIMEOUT = 10.0
DEFAULT_RUN_TIMEOUT = 30.0
VALID_PROVENANCE_KINDS = {
    'unspecified',
    'same_stack_fixture',
    'third_party_library',
    'third_party_binary',
    'package_owned',
}
VALID_EVIDENCE_TIERS = {'local_conformance', 'same_stack_replay', 'independent_certification', 'mixed'}
INTEROP_ARTIFACT_SCHEMA_VERSION = 1
QLOG_VERSION = '0.3'
INTEROP_BUNDLE_REQUIRED_FILES = (
    'manifest.json',
    'summary.json',
    'index.json',
)
INTEROP_SCENARIO_REQUIRED_FILES = (
    'summary.json',
    'index.json',
    'result.json',
    'scenario.json',
    'command.json',
    'env.json',
    'versions.json',
    'wire_capture.json',
)

__all__ = [name for name in globals() if not name.startswith('__')]
