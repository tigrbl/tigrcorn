from __future__ import annotations

from tigrcorn_protocols.resume import StreamResumeIdentity, StreamResumeRegistry


def test_stream_resume_t0_declares_identity_bound_record() -> None:
    registry = StreamResumeRegistry()
    identity = StreamResumeIdentity(
        client_id="client-a",
        session_id="session-a",
        stream_id="stream-a",
        binding="webtransport",
    )

    record = registry.register(token="rt-a", identity=identity, ttl_seconds=30, now=100.0)

    assert record.snapshot()["identity"] == identity.as_dict()
    assert record.snapshot()["state"] == "active"


def test_stream_resume_t1_accepts_matching_identity_and_replays_units() -> None:
    registry = StreamResumeRegistry()
    identity = StreamResumeIdentity(
        client_id="client-a",
        session_id="session-a",
        stream_id="stream-a",
        binding="h2",
    )
    registry.register(token="rt-a", identity=identity)
    registry.record_replay_unit("rt-a", b"first")
    registry.record_replay_unit("rt-a", b"second")
    registry.suspend("rt-a")

    decision = registry.resume(token="rt-a", identity=identity, requested_offset=1)

    assert decision.accepted is True
    assert decision.accepted_offset == 1
    assert decision.replay_units == (b"second",)
    assert decision.event() == {
        "type": "stream.resume.accept",
        "resume_token": "rt-a",
        "accepted_offset": 1,
        "replay_count": 1,
    }
