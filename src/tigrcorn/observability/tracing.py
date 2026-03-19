from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def span(name: str) -> Iterator[None]:
    yield
