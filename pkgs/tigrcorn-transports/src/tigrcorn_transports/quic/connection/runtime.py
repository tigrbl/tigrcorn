from __future__ import annotations

from .imports import *

class QuicConnectionRuntimeMixin:

    def _schedule_ack(self, packet_space: str, *, immediate: bool = False, now: float | None = None) -> None:
        normalized = self._recovery_space(packet_space)
        state = self._space_state(normalized)
        at = time.monotonic() if now is None else now
        state.pending_ack_eliciting += 1
        if immediate or normalized in {PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE} or state.pending_ack_eliciting >= 2:
            state.ack_deadline = at
        else:
            delay = self.local_transport_parameters.max_ack_delay / 1000.0 if self.local_transport_parameters is not None else _ACK_DELAY_DEFAULT
            state.ack_deadline = at + max(delay, 0.0)
        self._timer_wheel.schedule(_TIMER_ACK, state.ack_deadline, path_key=self._active_path_key, packet_space=normalized)

    def _clear_ack_schedule(self, packet_space: str) -> None:
        normalized = self._recovery_space(packet_space)
        state = self._space_state(normalized)
        state.pending_ack_eliciting = 0
        state.ack_deadline = None
        self._timer_wheel.cancel(_TIMER_ACK, path_key=self._active_path_key, packet_space=normalized)

    def _queue_scheduled_spec(
        self,
        *,
        packet_space: str,
        frames: list[object],
        token: bytes | None = None,
        path_key: Any | None = None,
        is_pto_probe: bool = False,
    ) -> None:
        self._scheduled_specs.append(
            _ScheduledFrameSpec(
                packet_space=packet_space,
                frames=list(frames),
                token=token,
                path_key=self._active_path_key if path_key is None else path_key,
                is_pto_probe=is_pto_probe,
            )
        )

    def _emit_scheduled_specs(self) -> list[bytes]:
        if not self._scheduled_specs:
            return []
        previous_path = self._active_path_key
        encoded_packets: list[tuple[str, bytes]] = []
        while self._scheduled_specs:
            spec = self._scheduled_specs.pop(0)
            self._activate_path(spec.path_key)
            encoded_packets.append(
                (
                    spec.packet_space,
                    self.send_frames(
                        spec.frames,
                        packet_space=spec.packet_space,
                        token=spec.token,
                        is_pto_probe=spec.is_pto_probe,
                    ),
                )
            )
        self._activate_path(previous_path)
        return self._pack_encoded_packets(encoded_packets)

    def _register_coalesced_datagrams(self, datagrams: Iterable[bytes]) -> None:
        for datagram in datagrams:
            if datagram in self._wire_datagram_packets:
                continue
            try:
                packets = split_coalesced_packets(datagram, destination_connection_id_length=max(len(self.local_cid), 1))
            except ProtocolError:
                continue
            refs: list[tuple[str, int]] = []
            for packet in packets:
                refs.extend(self._wire_datagram_packets.get(packet, []))
            if refs:
                self._wire_datagram_packets[datagram] = refs

    def _pack_encoded_packets(self, encoded_packets: list[tuple[str, bytes]]) -> list[bytes]:
        datagrams: list[bytes] = []
        long_header_group: list[bytes] = []

        def flush_long_group() -> None:
            nonlocal long_header_group
            if not long_header_group:
                return
            datagrams.extend(
                coalesce_packets(
                    long_header_group,
                    max_datagram_size=self._effective_send_datagram_size(),
                )
            )
            long_header_group = []

        for packet_space, raw in encoded_packets:
            if len(raw) > self._effective_send_datagram_size():
                raise ProtocolError('encoded QUIC packet exceeds effective UDP payload ceiling')
            if packet_space == PACKET_SPACE_APPLICATION:
                flush_long_group()
                datagrams.append(raw)
                continue
            long_header_group.append(raw)
        flush_long_group()
        self._register_coalesced_datagrams(datagrams)
        return datagrams

    def _acknowledgement_datagram(self, packet_space: str) -> bytes | None:
        normalized = self._recovery_space(packet_space)
        state = self._space_state(normalized)
        if not state.received_packets:
            self._clear_ack_schedule(normalized)
            return None
        raw = self.acknowledge(packet_space=normalized)
        self._clear_ack_schedule(normalized)
        return raw

    def _on_packets_lost(self, *, path_key: Any, packet_space: str, lost_numbers: Iterable[int]) -> None:
        unique_lost = sorted(set(lost_numbers))
        self.packets_lost_total += len(unique_lost)
        for packet_number in unique_lost:
            meta = self._sent_packets.pop((packet_space, packet_number), None)
            if meta is None:
                continue
            self._wire_datagram_packets.pop(meta.raw, None)
            recoverable = self._recovery_frames(
                meta.frames,
                record_abandonment=True,
            )
            if not recoverable:
                continue
            self._queue_scheduled_spec(
                packet_space=meta.packet_space,
                frames=recoverable,
                token=meta.token,
                path_key=path_key,
            )

    def _handle_ack_for_path(
        self,
        *,
        path_key: Any,
        packet_space: str,
        acked_numbers: list[int],
        ack_delay: float,
    ) -> None:
        if not acked_numbers:
            return
        recovery = self._path_state(path_key).recovery
        lost = recovery.on_ack_received(
            acked_numbers,
            ack_delay=ack_delay,
            packet_space=packet_space,
        )
        for packet_number in acked_numbers:
            meta = self._sent_packets.pop((packet_space, packet_number), None)
            if meta is not None:
                self._wire_datagram_packets.pop(meta.raw, None)
        self._on_packets_lost(path_key=path_key, packet_space=packet_space, lost_numbers=lost)
        if path_key == self._active_path_key:
            self._refresh_congestion_snapshot(recovery)

    def _handle_ack_frame(self, frame: QuicAckFrame, *, packet_space: str) -> None:
        normalized = self._recovery_space(packet_space)
        acked = frame.acknowledged_packets() or [frame.largest_acked]
        self.last_acked = max(self.last_acked, max(acked))
        ack_delay_exponent = self.peer_transport_parameters.ack_delay_exponent if self.peer_transport_parameters is not None else 3
        ack_delay = float(frame.ack_delay * (1 << ack_delay_exponent)) / 1_000_000 if frame.ack_delay else 0.0
        by_path: dict[Any, list[int]] = {}
        for packet_number in acked:
            meta = self._sent_packets.get((normalized, packet_number))
            if meta is None:
                continue
            by_path.setdefault(meta.path_key, []).append(packet_number)
        if not by_path:
            by_path[self._active_path_key] = acked
        for path_key, packet_numbers in by_path.items():
            self._handle_ack_for_path(
                path_key=path_key,
                packet_space=normalized,
                acked_numbers=packet_numbers,
                ack_delay=ack_delay,
            )
        self._update_runtime_timers()

    def _build_pto_probe_specs(self, *, path_key: Any) -> None:
        path_state = self._path_state(path_key)
        due_spaces = path_state.recovery.pto_due_spaces(now=time.monotonic())
        if not due_spaces:
            candidates = path_state.recovery.pto_candidates(now=time.monotonic())
            if not candidates:
                return
            earliest_deadline = min(deadline for _space, deadline in candidates)
            due_spaces = [space for space, deadline in candidates if abs(deadline - earliest_deadline) <= 0.001]
        self.pto_expirations_total += 1
        path_state.recovery.on_pto_expired()
        probes_sent = 0
        for space in due_spaces:
            outstanding = [
                meta
                for (packet_space, _packet_number), meta in self._sent_packets.items()
                if packet_space == space and meta.path_key == path_key
            ]
            outstanding.sort(key=lambda item: item.packet_number)
            if outstanding:
                for meta in outstanding:
                    recoverable = self._recovery_frames(meta.frames)
                    if not recoverable:
                        continue
                    self._queue_scheduled_spec(
                        packet_space=meta.packet_space,
                        frames=recoverable,
                        token=meta.token,
                        path_key=path_key,
                        is_pto_probe=True,
                    )
                    self.pto_probes_total += 1
                    probes_sent += 1
                    break
            else:
                probe_space = PACKET_SPACE_APPLICATION if space == PACKET_SPACE_APPLICATION else space
                self._queue_scheduled_spec(packet_space=probe_space, frames=[FRAME_PING], path_key=path_key, is_pto_probe=True)
                self.pto_probes_total += 1
                probes_sent += 1
            if probes_sent >= 2:
                break
        if probes_sent == 1:
            self._queue_scheduled_spec(packet_space=PACKET_SPACE_APPLICATION if due_spaces and due_spaces[0] == PACKET_SPACE_APPLICATION else (due_spaces[0] if due_spaces else PACKET_SPACE_APPLICATION), frames=[FRAME_PING], path_key=path_key, is_pto_probe=True)
            self.pto_probes_total += 1

    def _run_loss_detection(self, *, now: float | None = None) -> None:
        at = time.monotonic() if now is None else now
        for path_key, path_state in self._path_states.items():
            for packet_space, space in path_state.recovery.spaces.items():
                if space.loss_time is not None and space.loss_time <= at + 1e-9:
                    lost = path_state.recovery.detect_lost_packets(now=at, packet_space=packet_space)
                    self._on_packets_lost(path_key=path_key, packet_space=packet_space, lost_numbers=lost)
            if path_state.recovery.pto_due_spaces(now=at):
                self._build_pto_probe_specs(path_key=path_key)
            if path_key == self._active_path_key:
                self._refresh_congestion_snapshot(path_state.recovery)
        self._update_runtime_timers(now=at)

    def _update_runtime_timers(self, *, now: float | None = None) -> None:
        at = time.monotonic() if now is None else now
        for packet_space in (PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE, PACKET_SPACE_APPLICATION):
            state = self._space_state(packet_space)
            if state.ack_deadline is None:
                self._timer_wheel.cancel(_TIMER_ACK, path_key=self._active_path_key, packet_space=packet_space)
            else:
                self._timer_wheel.schedule(_TIMER_ACK, state.ack_deadline, path_key=self._active_path_key, packet_space=packet_space)
        for path_key, path_state in self._path_states.items():
            path_has_loss = False
            for packet_space, space in path_state.recovery.spaces.items():
                if space.loss_time is None:
                    self._timer_wheel.cancel(_TIMER_LOSS, path_key=path_key, packet_space=packet_space)
                    continue
                path_has_loss = True
                self._timer_wheel.schedule(_TIMER_LOSS, space.loss_time, path_key=path_key, packet_space=packet_space)
            if not path_has_loss:
                for packet_space in (PACKET_SPACE_INITIAL, PACKET_SPACE_HANDSHAKE, PACKET_SPACE_APPLICATION):
                    if path_state.recovery._space(packet_space).loss_time is None:
                        self._timer_wheel.cancel(_TIMER_LOSS, path_key=path_key, packet_space=packet_space)
            pto_delay = path_state.recovery.next_pto_deadline(now=at)
            if pto_delay is None:
                self._timer_wheel.cancel(_TIMER_PTO, path_key=path_key)
            else:
                self._timer_wheel.schedule(_TIMER_PTO, at + pto_delay, path_key=path_key)

    def next_runtime_deadline(self) -> float | None:
        return self._timer_wheel.next_delay()

    def drain_scheduled_datagrams(self) -> list[bytes]:
        due_datagrams: list[bytes] = []
        due_timers = self._timer_wheel.pop_due()
        if due_timers:
            for timer in due_timers:
                if timer.kind == _TIMER_ACK and timer.packet_space is not None:
                    raw = self._acknowledgement_datagram(timer.packet_space)
                    if raw is not None:
                        due_datagrams.append(raw)
                    continue
                if timer.kind == _TIMER_LOSS:
                    self._run_loss_detection(now=timer.deadline)
                    continue
                if timer.kind == _TIMER_PTO:
                    self._build_pto_probe_specs(path_key=timer.path_key)
                    self._update_runtime_timers(now=timer.deadline)
        due_datagrams.extend(self._emit_scheduled_specs())
        return due_datagrams

    def can_transmit_datagram(self, datagram: bytes, *, now: float | None = None) -> bool:
        at = time.monotonic() if now is None else now
        if len(datagram) > self._effective_send_datagram_size():
            return False
        if not self.can_send_amplification_limited(len(datagram)):
            return False
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return self.recovery.can_send(len(datagram), now=at)
        ack_eliciting_bytes_by_path: dict[Any, int] = {}
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or not meta.ack_eliciting:
                continue
            ack_eliciting_bytes_by_path[meta.path_key] = ack_eliciting_bytes_by_path.get(meta.path_key, 0) + len(meta.raw)
        if not ack_eliciting_bytes_by_path:
            return True
        for path_key, amount in ack_eliciting_bytes_by_path.items():
            if not self._path_state(path_key).recovery.can_send(amount, now=at):
                return False
        return True

    def next_transmit_delay(self, datagram: bytes, *, now: float | None = None) -> float | None:
        at = time.monotonic() if now is None else now
        if not self.can_send_amplification_limited(len(datagram)):
            return None
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return self.recovery.time_until_send(len(datagram), now=at)
        ack_eliciting_bytes_by_path: dict[Any, int] = {}
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or not meta.ack_eliciting:
                continue
            ack_eliciting_bytes_by_path[meta.path_key] = ack_eliciting_bytes_by_path.get(meta.path_key, 0) + len(meta.raw)
        if not ack_eliciting_bytes_by_path:
            return 0.0
        delays: list[float] = []
        for path_key, amount in ack_eliciting_bytes_by_path.items():
            delay = self._path_state(path_key).recovery.time_until_send(amount, now=at)
            if delay is None:
                return None
            delays.append(delay)
        return max(delays) if delays else 0.0

    def defer_datagram(self, datagram: bytes) -> bool:
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return False
        changed = False
        refunded = 0
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or not meta.transmitted:
                continue
            meta.transmitted = False
            refunded += len(meta.raw)
            if meta.ack_eliciting:
                self._path_state(meta.path_key).recovery.deactivate_packet(ref[1], packet_space=ref[0], now=time.monotonic())
            changed = True
        if changed:
            self.bytes_sent = max(0, self.bytes_sent - refunded)
            self._update_runtime_timers()
        return changed

    def confirm_datagram_sent(self, datagram: bytes, *, now: float | None = None) -> bool:
        refs = self._packet_refs_for_datagram(datagram)
        if not refs:
            return False
        at = time.monotonic() if now is None else now
        changed = False
        added = 0
        for ref in refs:
            meta = self._sent_packets.get(ref)
            if meta is None or meta.transmitted:
                continue
            meta.transmitted = True
            added += len(meta.raw)
            if meta.ack_eliciting:
                self._path_state(meta.path_key).recovery.activate_packet(ref[1], packet_space=ref[0], sent_time=at, now=at)
            changed = True
        if changed:
            self.bytes_sent += added
            self._update_runtime_timers(now=at)
        return changed
