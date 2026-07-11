from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from tigrcorn_core.errors import ProtocolError
from tigrcorn_transports.quic.crypto import (
    QuicPacketProtectionKeys,
    derive_initial_packet_protection_keys,
    derive_quic_packet_protection_keys,
    derive_secret,
    generate_connection_id,
    protect_quic_packet,
    unprotect_quic_packet,
    update_quic_secret,
)
from tigrcorn_transports.quic.flow import QuicFlowControl
from tigrcorn_transports.quic.handshake import HandshakeFlight, QuicTlsHandshakeDriver, TlsAlertError, TransportParameters
from tigrcorn_transports.quic.packets import (
    QuicLongHeaderPacket,
    QuicLongHeaderType,
    QuicRetryPacket,
    QuicShortHeaderPacket,
    QuicStatelessResetPacket,
    QuicVersionNegotiationPacket,
    coalesce_packets,
    decode_packet,
    split_coalesced_packets,
)
from tigrcorn_transports.quic.recovery import QuicLossRecovery
from tigrcorn_transports.quic.scheduler import QuicTimerWheel
from tigrcorn_transports.quic.streams import (
    FRAME_ACK,
    FRAME_CONNECTION_CLOSE,
    FRAME_CONNECTION_CLOSE_APP,
    FRAME_PADDING,
    FRAME_PING,
    QuicAckFrame,
    QuicConnectionCloseFrame,
    QuicCryptoFrame,
    QuicDataBlockedFrame,
    QuicDatagramFrame,
    QuicHandshakeDoneFrame,
    QuicMaxDataFrame,
    QuicMaxStreamDataFrame,
    QuicMaxStreamsFrame,
    QuicNewConnectionIdFrame,
    QuicNewTokenFrame,
    QuicPathChallengeFrame,
    QuicPathResponseFrame,
    QuicResetStreamFrame,
    QuicResetStreamAtFrame,
    QuicRetireConnectionIdFrame,
    QuicStopSendingFrame,
    QuicStreamDataBlockedFrame,
    QuicStreamFrame,
    QuicStreamManager,
    QuicStreamsBlockedFrame,
    decode_frame,
    encode_frame,
    frame_type_value,
    stream_is_local_initiated,
    stream_is_unidirectional,
    validate_frame_for_packet_space,
    validate_frames_for_packet_space,
)
from tigrcorn_core.utils.bytes import decode_quic_varint

from .model import *

__all__ = [name for name in globals() if not name.startswith("__")]
