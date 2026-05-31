from __future__ import annotations

import itertools

_counter = itertools.count(1)
_session_counter = itertools.count(1)
_stream_counter = itertools.count(1)


def next_id() -> int:
    return next(_counter)


def next_session_id() -> int:
    return next(_session_counter)


def next_stream_id() -> int:
    return next(_stream_counter)
