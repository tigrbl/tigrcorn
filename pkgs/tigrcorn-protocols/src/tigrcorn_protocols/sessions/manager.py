from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from tigrcorn_core.utils.ids import next_id

from .base import BaseSession


@dataclass(slots=True)
class SessionManager:
    sessions: dict[int, BaseSession] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def open(self, session: BaseSession | None = None, *, protocol: str = 'unknown') -> BaseSession:
        if session is None:
            session = BaseSession(session_id=next_id(), protocol=protocol)
        self.sessions[session.session_id] = session
        self.counts[session.protocol] += 1
        return session

    def close(self, session_id: int) -> None:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return
        session.close()
        self.counts[session.protocol] = max(0, self.counts[session.protocol] - 1)

    def snapshot(self) -> dict[str, int]:
        return dict(self.counts)
