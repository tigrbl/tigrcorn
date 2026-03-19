from __future__ import annotations

import signal
from collections.abc import Callable


def install_signal_handlers(loop, callback: Callable[[], None]) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, callback)
        except (NotImplementedError, RuntimeError):  # pragma: no cover - platform dependent
            try:
                signal.signal(sig, lambda *_: callback())
            except ValueError:
                pass
