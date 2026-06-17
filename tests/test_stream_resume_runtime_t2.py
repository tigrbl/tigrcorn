from __future__ import annotations

from tigrcorn_protocols.resume import StreamResumeIdentity, StreamResumeRegistry


def _identity(**overrides: str) -> StreamResumeIdentity:
    values = {
        "client_id": "client-a",
        "session_id": "session-a",
        "stream_id": "stream-a",
        "binding": "webtransport",
    }
    values.update(overrides)
    return StreamResumeIdentity(**values)


def test_stream_resume_t2_rejects_expired_and_identity_mismatch() -> None:
    registry = StreamResumeRegistry()
    identity = _identity()
    registry.register(token="rt-a", identity=identity, ttl_seconds=10, now=100.0)

    expired = registry.resume(token="rt-a", identity=identity, now=111.0)
    mismatch = registry.resume(
        token="rt-a",
        identity=_identity(client_id="client-b"),
        now=105.0,
    )

    assert expired.accepted is False
    assert expired.event()["reason"] == "expired"
    assert mismatch.accepted is False
    assert mismatch.event()["reason"] == "identity_mismatch"


def test_stream_resume_t2_rejects_stale_offsets_after_replay_window_trim() -> None:
    registry = StreamResumeRegistry(max_replay_units=2)
    identity = _identity(binding="h2")
    registry.register(token="rt-a", identity=identity)
    registry.record_replay_unit("rt-a", b"first")
    registry.record_replay_unit("rt-a", b"second")
    registry.record_replay_unit("rt-a", b"third")

    stale = registry.resume(token="rt-a", identity=identity, requested_offset=0)
    accepted = registry.resume(token="rt-a", identity=identity, requested_offset=1)

    assert stale.accepted is False
    assert stale.reason == "out_of_window"
    assert accepted.accepted is True
    assert accepted.accepted_offset == 1
    assert accepted.replay_units == (b"second", b"third")
    assert registry.snapshot()["rt-a"]["base_offset"] == 1


def test_stream_resume_t2_rejects_unknown_tokens_and_invalid_offsets() -> None:
    registry = StreamResumeRegistry()
    identity = _identity(binding="ws")
    registry.register(token="rt-a", identity=identity)

    assert registry.resume(token="missing", identity=identity).reason == "not_found"
    assert registry.resume(token="rt-a", identity=identity, requested_offset=-1).reason == "out_of_window"
    assert registry.resume(token="rt-a", identity=identity, requested_offset=1).reason == "out_of_window"
