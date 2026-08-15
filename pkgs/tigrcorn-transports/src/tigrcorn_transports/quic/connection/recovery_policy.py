from __future__ import annotations

from .imports import *


class QuicConnectionRecoveryPolicyMixin:
    def _ack_eliciting(self, frames: Iterable[object]) -> bool:
        return any(frame_is_ack_eliciting(frame) for frame in frames)

    def _regenerate_recovery_frame(self, frame: object) -> object:
        if isinstance(frame, QuicMaxDataFrame):
            return QuicMaxDataFrame(self.flow.local_connection_window)
        if isinstance(frame, QuicMaxStreamDataFrame):
            return QuicMaxStreamDataFrame(
                frame.stream_id,
                self.flow.receive_window_for_stream(frame.stream_id),
            )
        if isinstance(frame, QuicMaxStreamsFrame):
            return QuicMaxStreamsFrame(
                self.streams.local_max_streams(frame.bidirectional),
                bidirectional=frame.bidirectional,
            )
        if isinstance(frame, QuicDataBlockedFrame):
            return QuicDataBlockedFrame(self.flow.connection_window)
        if isinstance(frame, QuicStreamDataBlockedFrame):
            return QuicStreamDataBlockedFrame(
                frame.stream_id,
                self.flow.window_for_stream(frame.stream_id),
            )
        if isinstance(frame, QuicStreamsBlockedFrame):
            return QuicStreamsBlockedFrame(
                self.streams.peer_max_streams(frame.bidirectional),
                bidirectional=frame.bidirectional,
            )
        raise ValueError(f"cannot regenerate QUIC recovery state for {type(frame)!r}")

    def _recovery_frames(
        self,
        frames: Iterable[object],
        *,
        record_abandonment: bool = False,
    ) -> list[object]:
        recoverable: list[object] = []
        for frame in frames:
            disposition = recovery_disposition(frame)
            if disposition is RecoveryDisposition.ABANDON:
                if record_abandonment and isinstance(frame, QuicDatagramFrame):
                    self.datagram_frames_abandoned_total += 1
                continue
            if disposition is RecoveryDisposition.REGENERATE_STATE:
                frame = self._regenerate_recovery_frame(frame)
                self.frames_regenerated_total += 1
            if isinstance(frame, QuicStreamFrame):
                self.stream_bytes_retransmitted_total += len(frame.data)
            elif isinstance(frame, QuicCryptoFrame):
                self.crypto_bytes_retransmitted_total += len(frame.data)
            recoverable.append(frame)
        return recoverable


__all__ = ["QuicConnectionRecoveryPolicyMixin"]
