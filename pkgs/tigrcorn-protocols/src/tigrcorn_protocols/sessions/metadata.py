from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionMetadata:
    listener_name: str = 'default'
    transport: str = 'tcp'
    label: str = ''
