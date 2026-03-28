from __future__ import annotations

from pathlib import Path

from tigrcorn.static import StaticFilesApp

ROOT = Path(__file__).with_name('public')
app = StaticFilesApp(ROOT)
