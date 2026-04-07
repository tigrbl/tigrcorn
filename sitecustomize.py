from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TMP = ROOT / '.tmp' / 'py'
TMP.mkdir(parents=True, exist_ok=True)
for key in ('TMPDIR', 'TEMP', 'TMP'):
    os.environ[key] = str(TMP)
tempfile.tempdir = str(TMP)
