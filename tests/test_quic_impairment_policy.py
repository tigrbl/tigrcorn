from __future__ import annotations

import pytest

from tigrcorn.compat.interop_runner import (
    UDPImpairmentPolicy,
    UDPImpairmentProfile,
)


def test_udp_impairment_profile_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="drop_every"):
        UDPImpairmentProfile(drop_every=-1)
    with pytest.raises(ValueError, match="delay_seconds"):
        UDPImpairmentProfile(delay_seconds=-0.1)


def test_udp_impairment_policy_is_repeatable_per_direction() -> None:
    profile = UDPImpairmentProfile(drop_every=5, duplicate_every=3, reorder_every=2)

    def run() -> list[tuple[bytes, ...]]:
        policy = UDPImpairmentPolicy(profile)
        return [policy.apply("server_to_client", bytes([index])) for index in range(1, 7)]

    first = run()
    assert first == run()
    assert first[1] == ()
    assert first[2] == (b"\x03", b"\x02", b"\x03")
    assert first[4] == ()


def test_udp_impairment_policy_keeps_direction_state_independent() -> None:
    policy = UDPImpairmentPolicy(UDPImpairmentProfile(reorder_every=2))
    assert policy.apply("client_to_server", b"c1") == (b"c1",)
    assert policy.apply("client_to_server", b"c2") == ()
    assert policy.apply("server_to_client", b"s1") == (b"s1",)
    assert policy.apply("client_to_server", b"c3") == (b"c3", b"c2")
