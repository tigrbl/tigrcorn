from __future__ import annotations

import signal
from collections.abc import Callable
from types import FrameType
from typing import Any


SignalCallback = Callable[[int], None]


def install_signal_handlers(loop: Any, callback: Callable[[], None]) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, callback)
        except (NotImplementedError, RuntimeError):  # pragma: no cover - platform dependent
            try:
                signal.signal(sig, lambda *_: callback())
            except ValueError:
                pass


def install_sync_signal_handlers(callback: SignalCallback) -> dict[int, Any]:
    previous: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, lambda signum, frame, cb=callback: cb(signum))
    return previous


def restore_signal_handlers(previous: dict[int, Any]) -> None:
    for sig, handler in previous.items():
        signal.signal(sig, handler)
