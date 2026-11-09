from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release.checkpoints.rfc7692_independent_closure import *


if __name__ == '__main__':
    raise SystemExit(main())
