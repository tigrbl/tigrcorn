from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RequestTargetForm = Literal['origin', 'absolute', 'authority', 'asterisk']


@dataclass(slots=True)
class ParsedRequest:
    method: str
    target: str
    path: str
    raw_path: bytes
    query_string: bytes
    http_version: str
    headers: list[tuple[bytes, bytes]]
    body: bytes
    keep_alive: bool
    expect_continue: bool
    websocket_upgrade: bool


@dataclass(slots=True)
class ParsedRequestHead:
    method: str
    target: str
    path: str
    raw_path: bytes
    query_string: bytes
    http_version: str
    headers: list[tuple[bytes, bytes]]
    keep_alive: bool
    expect_continue: bool
    websocket_upgrade: bool
    body_kind: Literal['none', 'content-length', 'chunked']
    content_length: int | None
    target_form: RequestTargetForm
