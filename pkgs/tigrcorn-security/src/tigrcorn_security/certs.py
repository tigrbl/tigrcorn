from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PeerCertificate:
    subject: tuple | None = None
    issuer: tuple | None = None
    serial_number: str | None = None
