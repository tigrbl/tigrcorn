from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TLSPolicy:
    require_client_cert: bool = False
